#!/usr/bin/env python3
"""Bulk-enrich a tf-research-policy-aws YAML from the bundled managed-rule
metadata snapshot. Removes TODO placeholders for known managed rules in a
single deterministic pass — no per-rule WebFetch.

The snapshot lives at `references/managed-rules-metadata.json`. It maps each
`AWS Config managed rule identifier` (SCREAMING_SNAKE_CASE) to authoritative
fields (severity, condition.logic, remediation, etc.) extracted from the AWS
Config developer guide. Refresh it with `scripts/refresh_managed_rules_metadata.py`.

Behaviour:
  * For every rule whose `source.type` is `aws-config-managed-rule` and whose
    `source.identifier` is a key in the snapshot, populate any field that is
    currently empty or a TODO placeholder.
  * Never overwrites a non-TODO value unless --force is set.
  * Tags `provenance.<field>: aws-config-managed-rule-doc` for every field
    populated from the snapshot.
  * Reports two counts: rules enriched fully (no TODOs remain) and rules with
    residual TODOs (snapshot did not cover the field).
  * Exits non-zero if --require-zero-todos is set AND any TODO remains, so the
    workflow can fail fast in production runs.

Usage:
  scripts/bulk_enrich.py --yaml rules.yaml
  scripts/bulk_enrich.py --yaml rules.yaml --output enriched.yaml --require-zero-todos
  scripts/bulk_enrich.py --yaml rules.yaml --snapshot path/to/custom.json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import REFERENCES, is_todo, non_todo, safe_dump_yaml  # noqa: E402

import yaml  # noqa: E402

DEFAULT_SNAPSHOT = REFERENCES / "managed-rules-metadata.json"

# Legacy CFN type remap — keep this list in sync with parse_conformance_pack.py.
# bulk_enrich pulls resource_types from the bundled rules-metadata snapshot,
# which mirrors AWS Config developer-guide pages verbatim. Some pages still
# reference legacy CFN type names (AWS::OpenSearch::Domain, AWS::ACM::Certificate)
# even though the canonical CFN snapshot uses the renamed AWS::OpenSearchService::*
# / AWS::CertificateManager::* names. Without this remap, the snapshot would
# inject legacy names that validate_yaml.py then flags as 'not in CFN snapshot'.
# Loading from the same JSON keeps both scripts aligned.
def _load_legacy_cfn_type_remap() -> dict[str, str]:
    path = REFERENCES / "legacy-cfn-type-remap.json"
    if not path.is_file():
        return {}
    try:
        raw = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}
    return {k: v for k, v in raw.items() if not k.startswith("_") and isinstance(v, str)}


LEGACY_CFN_TYPE_REMAP = _load_legacy_cfn_type_remap()


def _remap_cfn_types(types: list[str]) -> list[str]:
    return [LEGACY_CFN_TYPE_REMAP.get(t, t) for t in types]

# Map snapshot field -> (yaml-path, optional inner key). yaml-path is dotted.
# When the inner key is None, the snapshot value replaces the dotted target
# wholesale; when set, the snapshot value lands at <dotted>.<inner>.
SNAPSHOT_TO_YAML: list[tuple[str, str, str | None]] = [
    ("title", "title", None),
    ("title", "framework_control", "title"),
    ("severity", "severity", None),
    ("service", "service", None),
    ("framework_control_requirement", "framework_control", "requirement"),
    ("condition_description", "condition", "description"),
    ("condition_logic", "condition", "logic"),
    ("remediation_summary", "remediation", "summary"),
    ("documentation_url", "source", "documentation_url"),
]


def get_dotted(rule: dict[str, Any], path: str) -> Any:
    cur: Any = rule
    for part in path.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def set_dotted(rule: dict[str, Any], path: str, inner: str | None, value: Any) -> bool:
    """Write value at rule[path] (or rule[path][inner]). Return True if changed."""
    parts = path.split(".")
    cur: dict[str, Any] = rule
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    last = parts[-1]
    if inner is None:
        if cur.get(last) == value:
            return False
        cur[last] = value
        return True
    inner_dict = cur.get(last)
    if not isinstance(inner_dict, dict):
        inner_dict = {}
        cur[last] = inner_dict
    if inner_dict.get(inner) == value:
        return False
    inner_dict[inner] = value
    return True


def tag_provenance(rule: dict[str, Any], field_path: str, source_value: str) -> None:
    """Set rule.provenance[field_path] = source_value preserving existing entries."""
    prov = rule.setdefault("provenance", {})
    if not isinstance(prov, dict):
        rule["provenance"] = {field_path: source_value}
        return
    existing = prov.get(field_path)
    if isinstance(existing, list):
        if source_value not in existing:
            existing.append(source_value)
    elif existing in (None, "", "unknown"):
        prov[field_path] = source_value
    elif existing != source_value:
        prov[field_path] = [existing, source_value]


def needs_fill(current: Any, force: bool) -> bool:
    if force:
        return True
    if current is None:
        return True
    if isinstance(current, str) and (not current.strip() or is_todo(current)):
        return True
    if isinstance(current, (list, dict)) and not current:
        return True
    return False


def enrich_resource_types(rule: dict[str, Any], snap_resource_types: list[str], force: bool) -> bool:
    """Fill resource_types from the snapshot.

    If the snapshot has resource_types, use them. If the snapshot's resource_types
    is empty (account-scoped rule like CLOUDTRAIL_SECURITY_TRAIL_ENABLED, SECURITYHUB_ENABLED,
    GUARDDUTY_ENABLED_CENTRALIZED) AND the rule currently has a TODO placeholder, fall back
    to `AWS::::Account` — the canonical pseudo-type for account-level Config evaluations.
    Otherwise leave the field alone.
    """
    current = rule.get("resource_types") or []
    if not isinstance(current, list):
        return False
    has_todo = any(is_todo(t) for t in current)
    is_empty = len(current) == 0

    if snap_resource_types:
        if not (force or is_empty or has_todo):
            return False
        rule["resource_types"] = list(snap_resource_types)
        return True

    # Snapshot has no resource_types and the YAML has a TODO. Account-scoped fallback.
    if has_todo or (force and is_empty):
        rule["resource_types"] = ["AWS::::Account"]
        return True
    return False


def enrich_parameters(rule: dict[str, Any], snap_parameters: dict[str, Any], force: bool) -> bool:
    """Merge snapshot parameters into source.parameters and condition.parameters."""
    if not snap_parameters:
        return False
    changed = False
    src = rule.setdefault("source", {})
    if isinstance(src, dict):
        existing = src.get("parameters")
        if existing in (None, {}, "") or force:
            src["parameters"] = dict(snap_parameters)
            changed = True
    return changed


def enrich_rule(rule: dict[str, Any], snap_entry: dict[str, Any], *, force: bool) -> dict[str, int]:
    """Enrich a single rule from a snapshot entry. Returns {filled, skipped}."""
    stats = {"filled": 0, "skipped": 0}
    for snap_key, yaml_path, inner in SNAPSHOT_TO_YAML:
        value = snap_entry.get(snap_key)
        if value in (None, ""):
            stats["skipped"] += 1
            continue
        target_path = f"{yaml_path}.{inner}" if inner else yaml_path
        current = get_dotted(rule, target_path)
        if needs_fill(current, force):
            if set_dotted(rule, yaml_path, inner, value):
                tag_provenance(rule, target_path, "aws-config-managed-rule-doc")
                stats["filled"] += 1
        else:
            stats["skipped"] += 1
    snap_resource_types = _remap_cfn_types(snap_entry.get("resource_types") or [])
    if enrich_resource_types(rule, snap_resource_types, force):
        tag_provenance(rule, "resource_types", "aws-config-managed-rule-doc")
        stats["filled"] += 1
    if enrich_parameters(rule, snap_entry.get("parameters") or {}, force):
        tag_provenance(rule, "source.parameters", "aws-config-managed-rule-doc")
        stats["filled"] += 1
    return stats


def enrich_process_check(rule: dict[str, Any], force: bool) -> dict[str, int]:
    """Enrich an AWS_CONFIG_PROCESS_CHECK custom rule.

    These rules — embedded in AWS conformance packs as `Source.Owner = AWS_CONFIG_PROCESS_CHECK`
    — are framework controls AWS cannot evaluate automatically (e.g., 'Ensure contact email is
    current'). They carry a human-readable description in the pack but no severity, no auto
    condition.logic, and no developer-guide page. We populate sensible fields and tag the
    provenance accurately so an auditor can distinguish process attestations from automated checks.

    Some packs (notably BNM RMiT) define process-check rules with NO Description field at all —
    just ConfigRuleName and Source. parse_conformance_pack leaves condition.description as a TODO
    in that case. We detect a TODO description and derive a human-readable title from the rule id
    (kebab-case → title-case) so the YAML still validates and reaches READY without manual cleanup.
    """
    stats = {"filled": 0, "skipped": 0}
    description = (rule.get("condition") or {}).get("description") or ""
    description_clean = description.strip()

    description_is_todo = is_todo(description_clean) if description_clean else False
    description_missing = not description_clean
    description_usable = description_clean and not description_is_todo

    # Derive a human-readable title from the rule id when no usable description is available
    # (e.g., 'response-plan-exists-maintained' -> 'Response plan exists maintained'). The rule id
    # is already a kebab-cased framework-control name in conformance packs, so it carries the
    # semantics needed for an auditor to read the requirement.
    rule_id = (rule.get("id") or "").strip()
    derived_title = rule_id.replace("-", " ").replace("_", " ").strip()
    derived_title = derived_title[:1].upper() + derived_title[1:] if derived_title else ""
    derived_requirement = (
        f"Process attestation: {derived_title}. AWS Config cannot evaluate this control "
        "automatically; manual verification and documented attestation required."
    ) if derived_title else ""

    # Replace a TODO description in-place with the derived requirement so downstream
    # bulk_enrich passes (count_residual_todos) see a populated description.
    cond_block = rule.setdefault("condition", {})
    if isinstance(cond_block, dict) and (description_missing or description_is_todo) and derived_requirement:
        cond_block["description"] = derived_requirement
        tag_provenance(rule, "condition.description", "manual-human")
        stats["filled"] += 1
        description_clean = derived_requirement
        description_usable = True

    if not description_usable:
        # Truly nothing to work with (no id either) — skip and leave to manual cleanup.
        return stats

    # Title from description (first sentence, kept short). Prefer the kebab-derived
    # title when the description is the verbose process-attestation boilerplate above.
    if needs_fill(rule.get("title"), force):
        title = derived_title or description_clean.split(".")[0][:140].strip()
        if title:
            rule["title"] = title
            tag_provenance(rule, "title", "aws-conformance-pack" if description_usable and not description_is_todo else "manual-human")
            stats["filled"] += 1

    fc = rule.setdefault("framework_control", {})
    if isinstance(fc, dict):
        if needs_fill(fc.get("title"), force) and rule.get("title"):
            fc["title"] = rule["title"]
            tag_provenance(rule, "framework_control.title", "aws-conformance-pack" if description_usable and not description_is_todo else "manual-human")
            stats["filled"] += 1
        if needs_fill(fc.get("requirement"), force):
            fc["requirement"] = description_clean
            tag_provenance(rule, "framework_control.requirement", "aws-conformance-pack" if description_usable and not description_is_todo else "manual-human")
            stats["filled"] += 1

    if needs_fill(rule.get("severity"), force):
        # Process checks have no AWS-published severity. INFORMATIONAL is the
        # honest default — auditors should know this can't be automatically failed.
        rule["severity"] = "INFORMATIONAL"
        tag_provenance(rule, "severity", "manual-human")
        stats["filled"] += 1

    cond = rule.setdefault("condition", {})
    if isinstance(cond, dict) and needs_fill(cond.get("logic"), force):
        cond["logic"] = "manual_attestation_required == true"
        tag_provenance(rule, "condition.logic", "manual-human")
        stats["filled"] += 1

    rem = rule.setdefault("remediation", {})
    if isinstance(rem, dict) and needs_fill(rem.get("summary"), force):
        rem["summary"] = (
            "Process control. Requires human attestation against the framework's stated criterion. "
            "See condition.description for the check; verify and document compliance manually."
        )
        tag_provenance(rule, "remediation.summary", "manual-human")
        stats["filled"] += 1

    src = rule.setdefault("source", {})
    if isinstance(src, dict) and needs_fill(src.get("documentation_url"), force):
        # Process checks have no developer-guide page. Use the conformance-pack repo as the
        # canonical reference since that's where the rule is defined.
        src["documentation_url"] = "https://github.com/awslabs/aws-config-rules/tree/master/aws-config-conformance-packs"
        tag_provenance(rule, "source.documentation_url", "aws-conformance-pack")
        stats["filled"] += 1

    if needs_fill(rule.get("service"), force):
        # Process checks aren't tied to a single service. Use 'config' as the catch-all.
        rule["service"] = "config"
        tag_provenance(rule, "service", "manual-human")
        stats["filled"] += 1

    rt = rule.get("resource_types") or []
    if isinstance(rt, list) and (force or any(is_todo(t) for t in rt) or not rt):
        # Process checks evaluate organisational state, not a CFN resource.
        rule["resource_types"] = ["AWS::::Account"]
        tag_provenance(rule, "resource_types", "manual-human")
        stats["filled"] += 1

    return stats


# Required field paths per validate_yaml.py — fields a TODO inside is a real gap.
# Anything else (test_cases[].name, framework_control.id, terraform_snippet, etc.) is
# scaffolding metadata and does NOT block validation. count_residual_todos must agree
# with the validator; otherwise the --require-zero-todos contract becomes incoherent.
_REQUIRED_PATHS: tuple[tuple[str, ...], ...] = (
    ("id",),
    ("title",),
    ("framework_control", "requirement"),
    ("severity",),
    ("service",),
    ("resource_types",),
    ("source", "type"),
    ("source", "identifier"),
    ("source", "documentation_url"),
    ("condition", "description"),
    ("condition", "logic"),
    ("remediation", "summary"),
    ("references",),
    ("test_cases",),
)


def count_residual_todos(rule: dict[str, Any]) -> int:
    count = 0
    for path in _REQUIRED_PATHS:
        cur: Any = rule
        for p in path:
            if not isinstance(cur, dict):
                cur = None
                break
            cur = cur.get(p)
        if isinstance(cur, str) and is_todo(cur):
            count += 1
        elif isinstance(cur, list):
            for it in cur:
                if isinstance(it, str) and is_todo(it):
                    count += 1
    return count


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaml", required=True, type=pathlib.Path)
    ap.add_argument("--output", type=pathlib.Path, help="default: in place")
    ap.add_argument("--snapshot", type=pathlib.Path, default=DEFAULT_SNAPSHOT)
    ap.add_argument("--force", action="store_true",
                    help="overwrite even non-TODO fields when snapshot has a value")
    ap.add_argument("--require-zero-todos", action="store_true",
                    help="exit non-zero if any TODO remains after enrichment")
    args = ap.parse_args()

    if not args.yaml.exists():
        print(f"ERROR: yaml not found: {args.yaml}", file=sys.stderr)
        return 2
    if not args.snapshot.exists():
        print(f"ERROR: snapshot not found: {args.snapshot}", file=sys.stderr)
        print("       run scripts/refresh_managed_rules_metadata.py to build it", file=sys.stderr)
        return 2

    doc = yaml.safe_load(args.yaml.read_text(encoding="utf-8"))
    if not isinstance(doc, dict):
        print("ERROR: yaml is not a mapping", file=sys.stderr)
        return 2

    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    rules = doc.get("rules") or []
    if not isinstance(rules, list):
        print("ERROR: rules is not a list", file=sys.stderr)
        return 2

    stats = collections.Counter()
    missing_ids: list[str] = []
    fully_enriched_rules = 0
    rules_with_residual_todos = 0

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        src = rule.get("source") or {}
        rule_type = src.get("type") or ""

        if rule_type == "aws-config-custom-rule":
            # Custom rules — typically AWS_CONFIG_PROCESS_CHECK in conformance packs.
            # Bulk-enrich what we can from the conformance-pack-derived description.
            ident = src.get("identifier") or ""
            if ident == "AWS_CONFIG_PROCESS_CHECK":
                rule_stats = enrich_process_check(rule, force=args.force)
                stats["filled"] += rule_stats["filled"]
                stats["skipped"] += rule_stats["skipped"]
                stats["custom_process_check_enriched"] += 1
            else:
                stats["custom_other"] += 1
            residual = count_residual_todos(rule)
            if residual == 0:
                fully_enriched_rules += 1
            else:
                rules_with_residual_todos += 1
            continue

        if rule_type != "aws-config-managed-rule":
            stats["skipped_non_managed"] += 1
            continue

        identifier = src.get("identifier") or ""
        snap_entry = snapshot.get(identifier)
        if not isinstance(snap_entry, dict):
            missing_ids.append(identifier)
            stats["missing_in_snapshot"] += 1
            continue

        rule_stats = enrich_rule(rule, snap_entry, force=args.force)
        stats["filled"] += rule_stats["filled"]
        stats["skipped"] += rule_stats["skipped"]
        stats["enriched_rules"] += 1
        residual = count_residual_todos(rule)
        if residual == 0:
            fully_enriched_rules += 1
        else:
            rules_with_residual_todos += 1

    out_path = args.output or args.yaml
    out_path.parent.mkdir(parents=True, exist_ok=True)
    safe_dump_yaml(doc, out_path)

    total_residual = sum(count_residual_todos(r) for r in rules if isinstance(r, dict))
    print(f"bulk_enrich: {stats['enriched_rules']} rules enriched from snapshot,",
          f"{stats['missing_in_snapshot']} rules missing from snapshot,",
          f"{stats['skipped_non_managed']} non-managed rules left alone")
    print(f"  fields filled: {stats['filled']}, fields kept (already populated): {stats['skipped']}")
    print(f"  fully-enriched rules (zero residual TODOs): {fully_enriched_rules}")
    print(f"  rules with residual TODOs: {rules_with_residual_todos}")
    print(f"  total TODO placeholders remaining across YAML: {total_residual}")
    if missing_ids:
        sample = sorted(set(missing_ids))[:8]
        print(f"  rules missing from snapshot (sample): {sample}")
        print("  refresh snapshot: scripts/refresh_managed_rules_metadata.py")

    if args.require_zero_todos and total_residual > 0:
        print("ERROR: --require-zero-todos set, but YAML still contains TODOs", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
