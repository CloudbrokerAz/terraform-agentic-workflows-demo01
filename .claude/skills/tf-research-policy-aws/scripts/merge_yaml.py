#!/usr/bin/env python3
"""Merge two YAML rule sets by framework_control.id.

Use case: build a "best of both" policy YAML by combining the
conformance-pack-derived skeleton (which has authoritative AWS Config
managed rule identifiers) with the Prowler-derived rule set (which has
verbatim framework requirement text, severity, terraform remediation,
and references).

Precedence rules (configurable via --primary):
  * `source.*` block        -- always wins from --primary side
  * `framework_control.*`   -- wins from the side whose value isn't TODO
  * `severity`              -- wins from the side whose value is in the enum
  * `remediation.*`         -- wins from the side that has non-TODO content
  * `references[]`          -- merged (deduplicated by URL)
  * `related_controls[]`    -- merged (deduplicated by framework+id)
  * `tags[]`                -- merged (deduplicated)
  * `test_cases[]`          -- prefer the side with executable inputs;
                               otherwise merge unique by name
  * `condition.{description,logic,parameters}` -- prefer non-TODO
  * `resource_types[]`      -- merged (deduplicated, drop TODO entries
                               if a real type exists)
  * `provenance`            -- propagated alongside each merged field;
                               supports plain and dotted keys; list values
                               deduped on insertion order

Rules in only one side are included with a `merge_status` note in the
top-level metadata block.

Usage:
  scripts/merge_yaml.py \
    --primary conformance-pack.yaml \
    --secondary prowler.yaml \
    --output merged.yaml
"""
from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Any

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import is_todo, non_todo, safe_dump_yaml  # noqa: E402


def index_by_control(rules: list[Any]) -> dict[str, list[dict[str, Any]]]:
    """Index rules by framework_control.id.

    framework_control.id is often a `TODO:` placeholder when the source conformance
    pack didn't structurally encode framework control IDs. Treating those TODOs as
    real keys causes spurious cross-framework collisions during merges (every
    'TODO: framework control ID...' rule looks identical). Instead, fall back to the
    rule's own `id` when framework_control.id is missing or a TODO — that keeps each
    rule independently keyed and prevents the merge from erroneously unifying them.
    """
    out: dict[str, list[dict[str, Any]]] = {}
    for r in rules:
        if not isinstance(r, dict):
            continue
        cid = ((r.get("framework_control") or {}).get("id"))
        cid_str = str(cid) if cid else ""
        if not cid_str or cid_str.startswith("TODO"):
            cid_str = str(r.get("id") or "")
        if not cid_str:
            continue
        out.setdefault(cid_str, []).append(r)
    return out


def merge_references(a: list[Any], b: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for src in (a or []) + (b or []):
        if not isinstance(src, dict):
            continue
        url = src.get("url") or ""
        if url and url not in seen:
            seen.add(url)
            out.append({"title": src.get("title") or "Reference", "url": url})
    return out


def merge_related(a: list[Any], b: list[Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for src in (a or []) + (b or []):
        if not isinstance(src, dict):
            continue
        key = (str(src.get("framework", "")), str(src.get("id", "")))
        if key not in seen and any(key):
            seen.add(key)
            out.append(src)
    return out


def merge_resource_types(a: list[Any], b: list[Any]) -> list[str]:
    real, todos = [], []
    for src in (a or []) + (b or []):
        if not isinstance(src, str):
            continue
        if is_todo(src):
            if src not in todos:
                todos.append(src)
        elif src not in real:
            real.append(src)
    return real if real else todos


def merge_test_cases(a: list[Any], b: list[Any]) -> list[Any]:
    def has_real_input(tc: Any) -> bool:
        if not isinstance(tc, dict):
            return False
        inp = tc.get("input")
        if not isinstance(inp, dict) or not inp:
            return False
        if "Resources" in inp:
            return True
        props = inp.get("properties")
        if isinstance(props, dict) and props:
            return True
        return False

    a_real = [tc for tc in (a or []) if has_real_input(tc)]
    b_real = [tc for tc in (b or []) if has_real_input(tc)]
    if a_real and not b_real:
        return a_real + [tc for tc in (b or []) if tc not in a_real]
    if b_real and not a_real:
        return b_real + [tc for tc in (a or []) if tc not in b_real]
    if a_real and b_real:
        out = list(a_real)
        names = {str(tc.get("name", "")) for tc in a_real}
        for tc in b_real:
            if str(tc.get("name", "")) not in names:
                out.append(tc)
        return out
    return (a or []) + [tc for tc in (b or []) if tc not in (a or [])]


# --- provenance helpers ---------------------------------------------------

# Per-field provenance dotted keys to consider during merge. We carry the
# union from both sides; provenance is data, not enforcement, and we want a
# truthful record of "where each side claimed each value came from."
PROVENANCE_KEYS = [
    "id", "title", "description",
    "framework_control", "framework_control.id", "framework_control.title", "framework_control.requirement",
    "related_controls",
    "severity", "service", "resource_types",
    "source", "source.type", "source.identifier", "source.documentation_url", "source.parameters",
    "security_hub",
    "condition", "condition.description", "condition.logic", "condition.parameters",
    "remediation", "remediation.summary", "remediation.terraform_snippet",
    "remediation.aws_cli_snippet", "remediation.console_steps", "remediation.notes",
    "references",
    "test_cases",
    "tags",
    # legacy unsplit keys carried by older YAMLs
    "source_identifier", "condition_description", "condition_logic", "remediation_terraform",
    "condition_parameters",
]


def _dedupe_list(values: list[Any]) -> list[Any]:
    """Order-preserving dedupe."""
    out: list[Any] = []
    for v in values:
        if v not in out:
            out.append(v)
    return out


def _merge_prov_value(p: Any, s: Any) -> Any:
    """Combine two provenance values for the same key."""
    if p is None or p == []:
        return s
    if s is None or s == []:
        return p
    p_list = p if isinstance(p, list) else [p]
    s_list = s if isinstance(s, list) else [s]
    if p_list == s_list:
        return p
    merged = _dedupe_list([*p_list, *s_list])
    return merged[0] if len(merged) == 1 else merged


def merge_provenance(
    primary: dict[str, Any], secondary: dict[str, Any]
) -> dict[str, Any]:
    """Combine the provenance blocks of two rules.

    Strategy: union of keys. For shared keys, dedupe-merge to a single string
    or list. Both flat and dotted keys are preserved as-given. Future tooling
    that wants just-the-flat or just-the-dotted view can normalise from this.
    """
    p_prov = primary.get("provenance") if isinstance(primary.get("provenance"), dict) else {}
    s_prov = secondary.get("provenance") if isinstance(secondary.get("provenance"), dict) else {}
    keys = sorted({*p_prov.keys(), *s_prov.keys()})
    out: dict[str, Any] = {}
    for k in keys:
        if not isinstance(k, str) or k.startswith("_"):
            continue
        out[k] = _merge_prov_value(p_prov.get(k), s_prov.get(k))
    return out


def merge_rules(primary: dict[str, Any], secondary: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # id, title -- prefer primary unless TODO
    out["id"] = primary.get("id") if non_todo(primary.get("id")) else secondary.get("id") or primary.get("id")
    out["title"] = (
        primary.get("title") if non_todo(primary.get("title"))
        else secondary.get("title") or primary.get("title")
    )

    # framework_control: union, prefer non-TODO per-field
    fc_p = primary.get("framework_control") or {}
    fc_s = secondary.get("framework_control") or {}
    fc_out: dict[str, Any] = {}
    for key in ("id", "title", "requirement"):
        fc_out[key] = (
            fc_p.get(key) if non_todo(fc_p.get(key))
            else (fc_s.get(key) if non_todo(fc_s.get(key)) else fc_p.get(key) or fc_s.get(key))
        )
    out["framework_control"] = {k: v for k, v in fc_out.items() if v is not None}

    # related_controls
    related = merge_related(primary.get("related_controls") or [], secondary.get("related_controls") or [])
    if related:
        out["related_controls"] = related

    # severity
    p_sev = primary.get("severity")
    s_sev = secondary.get("severity")
    valid = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
    if p_sev in valid:
        out["severity"] = p_sev
    elif s_sev in valid:
        out["severity"] = s_sev
    else:
        out["severity"] = p_sev or s_sev

    # service
    out["service"] = (
        primary.get("service") if non_todo(primary.get("service"))
        else secondary.get("service") or primary.get("service")
    )

    # resource_types
    out["resource_types"] = merge_resource_types(
        primary.get("resource_types") or [], secondary.get("resource_types") or []
    )

    # source -- always primary's, since it carries the managed-rule identifier
    out["source"] = primary.get("source") or secondary.get("source") or {}

    # security_hub mapping if present
    if primary.get("security_hub") or secondary.get("security_hub"):
        out["security_hub"] = primary.get("security_hub") or secondary.get("security_hub")

    # condition -- per-field non-TODO preference
    cond_p = primary.get("condition") or {}
    cond_s = secondary.get("condition") or {}
    cond_out: dict[str, Any] = {}
    for key in ("description", "logic"):
        cond_out[key] = (
            cond_p.get(key) if non_todo(cond_p.get(key))
            else (cond_s.get(key) if non_todo(cond_s.get(key)) else cond_p.get(key) or cond_s.get(key))
        )
    cond_out["parameters"] = cond_p.get("parameters") or cond_s.get("parameters") or {}
    out["condition"] = cond_out

    # remediation -- prefer richer side per-field
    rem_p = primary.get("remediation") or {}
    rem_s = secondary.get("remediation") or {}
    rem_out: dict[str, Any] = {}
    for key in ("summary", "terraform_snippet", "aws_cli_snippet", "notes"):
        if non_todo(rem_p.get(key)):
            rem_out[key] = rem_p.get(key)
        elif non_todo(rem_s.get(key)):
            rem_out[key] = rem_s.get(key)
        elif rem_p.get(key) or rem_s.get(key):
            rem_out[key] = rem_p.get(key) or rem_s.get(key)
    if rem_p.get("console_steps") or rem_s.get("console_steps"):
        rem_out["console_steps"] = rem_p.get("console_steps") or rem_s.get("console_steps")
    out["remediation"] = rem_out

    # references -- merge
    refs = merge_references(primary.get("references") or [], secondary.get("references") or [])
    if refs:
        out["references"] = refs

    # test_cases
    out["test_cases"] = merge_test_cases(primary.get("test_cases") or [], secondary.get("test_cases") or [])

    # tags
    tags = []
    seen_tags = set()
    for t in (primary.get("tags") or []) + (secondary.get("tags") or []):
        if isinstance(t, str) and t not in seen_tags:
            seen_tags.add(t)
            tags.append(t)
    if tags:
        out["tags"] = tags

    # provenance — union with dedupe-merge per key. Required for the audit trail
    # to survive merge; without this, --strict-aws-official can't tell whether
    # the merged YAML still contains third-party content.
    prov = merge_provenance(primary, secondary)
    if prov:
        out["provenance"] = prov

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--primary", type=pathlib.Path, required=True,
                        help="primary YAML (e.g., conformance-pack-derived)")
    parser.add_argument("--secondary", type=pathlib.Path, required=True,
                        help="secondary YAML (e.g., Prowler-derived)")
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args()

    primary_doc = yaml.safe_load(args.primary.read_text(encoding="utf-8"))
    secondary_doc = yaml.safe_load(args.secondary.read_text(encoding="utf-8"))

    primary_rules = primary_doc.get("rules") or []
    secondary_rules = secondary_doc.get("rules") or []

    primary_idx = index_by_control(primary_rules)
    secondary_idx = index_by_control(secondary_rules)

    merged: list[dict[str, Any]] = []
    matched_secondary_keys: set[str] = set()

    def _resolve_key(rule: dict[str, Any]) -> str:
        """Mirror index_by_control: fall back to rule.id when framework_control.id is TODO."""
        cid = ((rule.get("framework_control") or {}).get("id"))
        cid_str = str(cid) if cid else ""
        if not cid_str or cid_str.startswith("TODO"):
            cid_str = str(rule.get("id") or "")
        return cid_str

    # Pass 1: primary rules, possibly enriched by secondary
    for rule in primary_rules:
        if not isinstance(rule, dict):
            continue
        key = _resolve_key(rule)
        if key and key in secondary_idx:
            sec = secondary_idx[key][0]
            merged.append(merge_rules(rule, sec))
            matched_secondary_keys.add(key)
        else:
            merged.append(rule)

    # Pass 2: secondary rules with no primary match
    only_secondary = []
    for cid, rules in secondary_idx.items():
        if cid in matched_secondary_keys:
            continue
        for r in rules:
            r = dict(r)
            r["merge_status"] = "from secondary; no matching control id in primary"
            only_secondary.append(r)
    merged.extend(only_secondary)

    only_primary_count = sum(
        1 for r in primary_rules
        if isinstance(r, dict) and _resolve_key(r) not in secondary_idx
    )

    out_doc = {
        "metadata": {
            **(primary_doc.get("metadata") or {}),
            "merged_with": str(args.secondary),
            "merge_summary": {
                "total_rules": len(merged),
                "matched_both_sides": len(matched_secondary_keys),
                "only_in_primary": only_primary_count,
                "only_in_secondary": len(only_secondary),
            },
        },
        "rules": merged,
    }
    safe_dump_yaml(out_doc, args.output)
    print(f"wrote {len(merged)} rules to {args.output}", file=sys.stderr)
    print(
        f"  matched both: {len(matched_secondary_keys)}, "
        f"only primary: {only_primary_count}, "
        f"only secondary: {len(only_secondary)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
