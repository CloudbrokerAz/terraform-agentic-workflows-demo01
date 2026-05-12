#!/usr/bin/env python3
"""Merge AWS-API-fetched control metadata into a YAML rule skeleton.

Inputs:
  * a YAML skeleton produced by parse_conformance_pack.py (or a hand-written one)
  * a JSON file produced by fetch_security_hub_controls.py or fetch_audit_manager_framework.py

Behavior:
  * Tries to match each YAML rule to a fetched control via Security Hub
    related_requirements (which often reference the AWS Config rule slug),
    via control_id substring match in the rule's source.identifier, or via
    name/title fuzzy match.
  * For matched rules, populates: severity, framework_control.title,
    framework_control.requirement (from Description), references (adds
    remediation_url), and related_controls (from related_requirements).
  * Never overwrites a non-TODO field unless --force is given.
  * Reports unmatched controls and unmatched rules separately.
  * Exits non-zero on zero matches unless --allow-empty is passed.

Usage:
  scripts/enrich_yaml.py --yaml rules.yaml --controls security-hub.json --output enriched.yaml
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import REFERENCES, is_todo, kebab as _kebab, safe_dump_yaml  # noqa: E402

import yaml  # noqa: E402

DEFAULT_CROSSWALK = REFERENCES / "sh-control-to-config-rule.json"


def load_crosswalk(path: pathlib.Path | None) -> dict[str, str]:
    """Load Security Hub control_id -> AWS Config managed-rule kebab slug mapping.

    Used by Strategy 0 in match_rule(). Lets enrich_yaml work in `--unsubscribed`
    mode (catalogue view) where Security Hub returns empty RelatedRequirements.
    Without this map, no rules in the YAML skeleton can be linked back to their
    Security Hub control unless the rule.id already encodes the control ID.
    """
    target = path if path is not None else DEFAULT_CROSSWALK
    if not target.exists():
        return {}
    raw = json.loads(target.read_text(encoding="utf-8"))
    return {
        k: v
        for k, v in raw.items()
        if isinstance(k, str) and isinstance(v, str) and not k.startswith("_")
    }


def slugify(s: str) -> str:
    return _kebab(s)


def parse_related_requirements(reqs: list[str]) -> list[dict[str, str]]:
    """Convert Security Hub RelatedRequirements strings into structured related_controls entries.

    Examples of what arrives in `reqs`:
      "NIST.800-53.r5 SC-28"
      "PCI DSS v4.0 3.5.1"
      "CIS AWS Foundations Benchmark v1.4.0/2.3.1"
    """
    out = []
    for r in reqs or []:
        r = r.strip()
        if "/" in r:
            framework, control = r.rsplit("/", 1)
        else:
            parts = r.split(maxsplit=1)
            if len(parts) == 2:
                framework, control = parts
            else:
                continue
        out.append({"framework": framework.strip(), "id": control.strip()})
    return out


def index_security_hub_controls(controls: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Index controls by every plausible lookup key."""
    idx: dict[str, dict[str, Any]] = {}
    for c in controls:
        cid = (c.get("control_id") or "").strip()
        if cid:
            idx[cid.lower()] = c
        title_slug = slugify(c.get("title") or "")
        if title_slug and title_slug not in idx:
            idx[title_slug] = c
    return idx


def match_rule(
    rule: dict[str, Any],
    controls: list[dict[str, Any]],
    idx: dict[str, dict[str, Any]],
    crosswalk: dict[str, str] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Try multiple match strategies in order of confidence.

    Returns (control, strategy_name) or (None, None).

    Match strategies, in order:
      0. Curated Security Hub control_id -> Config rule crosswalk lookup. Wins
         in `--unsubscribed` mode where the catalogue view returns empty
         RelatedRequirements but the bundled crosswalk knows the mapping.
      1. Security Hub control_id is part of rule.id (legacy CIS-style packs).
      2. rule.source.identifier (kebab) appears in a control's RelatedRequirements
         (works in subscribed mode where the field is populated).
      3. rule.source.identifier appears anywhere in the control's description
         AS A WHOLE WORD MATCH (works in unsubscribed catalogue mode). If
         multiple controls match, returns no result and falls through to
         strategy 4 - description references can be ambiguous, and silently
         picking the first hit produces non-deterministic provenance.
      4. Slugified title vs slugified rule.id fallback.
    """
    rid = rule.get("id") or ""
    src_id_screaming = ((rule.get("source") or {}).get("identifier") or "")
    src_id_kebab = src_id_screaming.replace("_", "-").lower()

    # Strategy 0: curated crosswalk control_id -> Config rule slug
    if crosswalk and src_id_kebab:
        for c in controls:
            cid = c.get("control_id") or ""
            mapped = crosswalk.get(cid)
            if mapped and mapped == src_id_kebab:
                return c, "crosswalk"

    # Strategy 1: SH control_id embedded in rule.id (RDS.3 -> "rds-3")
    for c in controls:
        cid = (c.get("control_id") or "").lower()
        if cid and (cid in rid.lower() or cid.replace(".", "-") in rid.lower()):
            return c, "rule-id-substring"

    # Strategy 2: src identifier (kebab) appears in related_requirements (subscribed mode)
    for c in controls:
        for req in c.get("related_requirements") or []:
            if src_id_kebab and src_id_kebab in req.lower():
                return c, "related-requirements"

    # Strategy 3: src identifier embedded in description as a whole word
    if src_id_kebab:
        # Whole-word match avoids "rds-encrypted" matching "rds-encrypted-at-rest".
        kebab_re = re.compile(rf"(?<![a-z0-9-]){re.escape(src_id_kebab)}(?![a-z0-9-])", re.IGNORECASE)
        screaming_re = re.compile(rf"(?<![A-Z0-9_]){re.escape(src_id_screaming)}(?![A-Z0-9_])")
        candidates = [
            c
            for c in controls
            if isinstance(c.get("description"), str)
            and (kebab_re.search(c["description"]) or screaming_re.search(c["description"]))
        ]
        if len(candidates) == 1:
            return candidates[0], "description-whole-word"
        # Ambiguous (multiple) or no hit - fall through. Caller logs.

    # Strategy 4: slugified title vs slugified rule.id
    rid_slug = slugify(rid)
    if rid_slug in idx:
        return idx[rid_slug], "title-slug"
    return None, None


def _record_provenance(provenance: dict[str, Any], key: str, source_label: str) -> None:
    """Record `source_label` against provenance[key]. Lists are deduplicated; scalars promote to lists on second source."""
    existing = provenance.get(key)
    if existing is None:
        provenance[key] = source_label
        return
    if isinstance(existing, list):
        if source_label not in existing:
            existing.append(source_label)
        return
    if existing == source_label:
        return
    provenance[key] = [existing, source_label]


def apply_security_hub(
    rule: dict[str, Any],
    control: dict[str, Any],
    force: bool,
    *,
    source_label: str = "aws-security-hub",
    match_strategy: str | None = None,
) -> list[str]:
    """Mutate `rule` with control metadata. Return list of fields populated.

    `source_label` is recorded in the rule's `provenance` block for each field updated.
    When the match was driven by the curated crosswalk, the provenance is recorded as
    the list `[source_label, manual-human]` because the *content* is from AWS but the
    *linkage* came from a hand-curated map.
    """
    populated: list[str] = []
    provenance = rule.setdefault("provenance", {})
    # The curated crosswalk is hand-maintained; record both the content origin and
    # the linkage origin so an auditor can filter for either.
    labels: list[str] = (
        [source_label, "manual-human"] if match_strategy == "crosswalk" else [source_label]
    )

    def set_if_todo_or_force(
        container: dict[str, Any], key: str, value: Any, prov_key: str | None = None
    ) -> None:
        if value in (None, ""):
            return
        if force or is_todo(container.get(key)) or container.get(key) in (None, ""):
            container[key] = value
            populated.append(key)
            if prov_key:
                for label in labels:
                    _record_provenance(provenance, prov_key, label)

    # severity
    set_if_todo_or_force(rule, "severity", control.get("severity"), prov_key="severity")

    # framework_control sub-fields get their own dotted provenance keys so the
    # title from SH doesn't overwrite the .id from the conformance pack.
    fc = rule.setdefault("framework_control", {})
    set_if_todo_or_force(fc, "title", control.get("title"), prov_key="framework_control.title")
    set_if_todo_or_force(
        fc, "requirement", control.get("description"), prov_key="framework_control.requirement"
    )

    # related_controls
    related = parse_related_requirements(control.get("related_requirements") or [])
    if related and (force or not rule.get("related_controls")):
        rule["related_controls"] = related
        populated.append("related_controls")
        for label in labels:
            _record_provenance(provenance, "related_controls", label)

    # references — append remediation URL if not already present (idempotent)
    refs = rule.setdefault("references", [])
    remediation_url = control.get("remediation_url")
    if remediation_url and not any(r.get("url") == remediation_url for r in refs if isinstance(r, dict)):
        refs.append(
            {
                "title": f"Security Hub control {control.get('control_id')} remediation",
                "url": remediation_url,
            }
        )
        populated.append("references")
        for label in labels:
            _record_provenance(provenance, "references", label)

    # security_hub mapping block
    if control.get("control_id") and (force or not rule.get("security_hub")):
        rule["security_hub"] = {
            "control_id": control.get("control_id"),
            "documentation_url": control.get("remediation_url") or "",
        }
        populated.append("security_hub")
        for label in labels:
            _record_provenance(provenance, "security_hub", label)

    return populated


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yaml", type=pathlib.Path, required=True, help="rule skeleton YAML")
    parser.add_argument("--controls", type=pathlib.Path, required=True, help="JSON from fetch_*")
    parser.add_argument("--output", type=pathlib.Path, help="output path (default: in-place rewrite)")
    parser.add_argument("--force", action="store_true", help="overwrite existing non-TODO values")
    parser.add_argument(
        "--source",
        default="aws-security-hub",
        choices=["aws-security-hub", "aws-audit-manager"],
        help="provenance label written to the rule for fields enriched in this run",
    )
    parser.add_argument(
        "--crosswalk",
        type=pathlib.Path,
        default=None,
        help="path to control_id -> Config rule crosswalk JSON (default: bundled "
             "references/sh-control-to-config-rule.json). Pass --no-crosswalk to disable.",
    )
    parser.add_argument(
        "--no-crosswalk",
        action="store_true",
        help="disable the curated control_id -> Config rule crosswalk",
    )
    parser.add_argument(
        "--allow-empty",
        action="store_true",
        help="exit 0 even when zero rules matched (default: exit 1 on zero matches)",
    )
    args = parser.parse_args()

    doc = yaml.safe_load(args.yaml.read_text(encoding="utf-8"))
    controls_data = json.loads(args.controls.read_text(encoding="utf-8"))
    controls = controls_data.get("controls") or []
    idx = index_security_hub_controls(controls)
    crosswalk = {} if args.no_crosswalk else load_crosswalk(args.crosswalk)
    if crosswalk:
        print(f"loaded crosswalk: {len(crosswalk)} control_id -> Config rule entries", file=sys.stderr)

    rules = doc.get("rules") or []
    matched = 0
    unmatched_rules: list[str] = []
    matched_control_ids: set[str] = set()
    strategy_counts: dict[str, int] = {}

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        c, strategy = match_rule(rule, controls, idx, crosswalk=crosswalk)
        if not c:
            unmatched_rules.append(rule.get("id") or "<no id>")
            continue
        matched += 1
        if strategy:
            strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1
        matched_control_ids.add(c.get("control_id") or "")
        apply_security_hub(rule, c, args.force, source_label=args.source, match_strategy=strategy)

    unmatched_controls = [
        c.get("control_id")
        for c in controls
        if c.get("control_id") and c.get("control_id") not in matched_control_ids
    ]

    out_path = args.output or args.yaml
    safe_dump_yaml(doc, out_path)
    total = len(rules)
    pct = (matched / total * 100) if total else 0.0
    print(f"matched {matched}/{total} rules ({pct:.0f}%)", file=sys.stderr)
    if strategy_counts:
        breakdown = ", ".join(f"{s}={n}" for s, n in sorted(strategy_counts.items(), key=lambda kv: -kv[1]))
        print(f"  by strategy: {breakdown}", file=sys.stderr)
    if unmatched_rules:
        print(
            f"  unmatched rules: {', '.join(unmatched_rules[:10])}"
            f"{'...' if len(unmatched_rules) > 10 else ''}",
            file=sys.stderr,
        )
    if unmatched_controls:
        print(
            f"  unmatched controls (not in skeleton): {len(unmatched_controls)}; "
            f"first 10: {', '.join(unmatched_controls[:10])}",
            file=sys.stderr,
        )
    print(f"wrote {out_path}", file=sys.stderr)

    if total and matched == 0 and not args.allow_empty:
        print(
            "FAIL: zero rules matched. Likely causes: wrong --controls input, missing crosswalk "
            "entry, or the conformance pack uses identifiers the catalogue mode doesn't expose. "
            "Re-run with --allow-empty to override; otherwise inspect a few unmatched rule IDs "
            "vs. unmatched control IDs and either fix the skeleton or extend the crosswalk.",
            file=sys.stderr,
        )
        return 1
    if total and pct < 50 and not args.allow_empty:
        print(
            f"warning: only {pct:.0f}% of rules matched. Continuing (use --allow-empty to silence). "
            "If you proceed without diagnosing, downstream Phase-4 enrichment will be against a "
            "skeleton that's mostly unenriched.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
