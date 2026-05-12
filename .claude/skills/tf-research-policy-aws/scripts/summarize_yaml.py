#!/usr/bin/env python3
"""Summarize a tf-research-policy-aws YAML output for reporting.

Reports:
  * total rule count
  * gap count (custom rules + null severities + TODO placeholders remaining)
  * severity histogram
  * service breakdown
  * source.type histogram

Usage:
  scripts/summarize_yaml.py <file>
  scripts/summarize_yaml.py <file> --json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import sys
from typing import Any

import yaml


def is_todo(value: Any) -> bool:
    return isinstance(value, str) and value.strip().startswith("TODO")


# These keys are optional per the schema (validate_yaml.py does not require them).
# Counting them as TODO blockers caused friction — runs that already passed
# validation showed nonzero gap counts because the conformance-pack scaffold
# inserted "TODO: minimal compliant HCL" into terraform_snippet. summarize_yaml
# now skips these so total_todo_placeholders aligns with what validate_yaml will
# actually fail on.
OPTIONAL_KEYS_SKIP: set[str] = {
    "terraform_snippet",
    "aws_cli_snippet",
    "console_steps",
    "notes",
    "description",  # rule.description is optional; only condition.description is required
    "tags",
    "scope",
    "related_controls",
    # framework_control.id and framework_control.title are *not* required by validate_yaml.py.
    # framework_control.requirement IS required. Counting id/title as gaps misled multiple
    # workflow runs into believing the file was NOT READY when validate_yaml accepted it.
    "id",
    # NOTE: this skip applies broadly. summarize_yaml walks recursively, so suppressing 'id' here
    # also drops rule-level 'id' from the gap count — but that's required, so the call site below
    # only suppresses when parent_key indicates we're inside an optional subtree.
    # See _is_optional_path for the actual decision.
}

# Required field paths per validate_yaml.py. Any TODO inside these IS a real gap.
# Anything else is treated as scaffolding metadata and ignored by the gap counter.
REQUIRED_PATHS: set[tuple[str, ...]] = {
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
}


def count_todos(rule: dict[str, Any]) -> int:
    """Count TODOs that will block validation. Mirrors validate_yaml.check_required.

    A TODO inside a path NOT in REQUIRED_PATHS (e.g., framework_control.id,
    test_cases[].name) is scaffolding metadata, not a real gap. Counting those
    in the past misled the workflow into reporting NOT READY for files that
    validate_yaml accepted. The gap counter must agree with the validator;
    that is the whole point of the READY/NOT-READY verdict.
    """
    todos = 0

    def get_required_value(path: tuple[str, ...]) -> Any:
        cur: Any = rule
        for p in path:
            if not isinstance(cur, dict):
                return None
            cur = cur.get(p)
        return cur

    for path in REQUIRED_PATHS:
        v = get_required_value(path)
        if isinstance(v, str) and is_todo(v):
            todos += 1
        elif isinstance(v, list):
            # references and test_cases: count list-item TODO scalars only at the surface,
            # not inside test_cases[].name etc. (those are not required by the validator).
            for it in v:
                if isinstance(it, str) and is_todo(it):
                    todos += 1
    return todos


def summarize(doc: dict[str, Any]) -> dict[str, Any]:
    rules = doc.get("rules") or []
    severities: collections.Counter = collections.Counter()
    services: collections.Counter = collections.Counter()
    source_types: collections.Counter = collections.Counter()
    gap_custom = 0
    gap_severity = 0
    rules_with_todos = 0
    total_todos = 0

    for r in rules:
        if not isinstance(r, dict):
            continue
        sev = r.get("severity")
        if sev in (None, "") or is_todo(sev):
            severities["UNSET"] += 1
            gap_severity += 1
        else:
            severities[str(sev)] += 1

        services[str(r.get("service") or "UNSET")] += 1
        st = ((r.get("source") or {}).get("type")) or "UNSET"
        source_types[str(st)] += 1
        if st == "aws-config-custom-rule":
            # NOTE: this counts custom rules, NOT deliverable gaps.
            # Custom rules (especially AWS_CONFIG_PROCESS_CHECK process attestations)
            # are first-class outputs after bulk_enrich.py auto-fills their fields.
            # The name predates that automation; kept for backwards-compatibility.
            gap_custom += 1

        n_todos = count_todos(r)
        if n_todos:
            rules_with_todos += 1
            total_todos += n_todos

    return {
        "metadata": doc.get("metadata") or {},
        "totals": {
            "rules": len(rules),
            "rules_with_todos": rules_with_todos,
            "total_todo_placeholders": total_todos,
            "gap_custom_rules": gap_custom,
            "gap_unset_severity": gap_severity,
        },
        "severity_histogram": dict(severities.most_common()),
        "service_breakdown": dict(services.most_common()),
        "source_type_histogram": dict(source_types.most_common()),
    }


def is_ready(summary: dict[str, Any]) -> bool:
    """READY when nothing the validator would reject remains. Mirrors validate_yaml.py."""
    t = summary["totals"]
    return t["total_todo_placeholders"] == 0 and t["gap_unset_severity"] == 0


def render_text(summary: dict[str, Any]) -> str:
    meta = summary["metadata"]
    fw = meta.get("framework") or {}
    lines = [
        f"Framework: {fw.get('name', '?')} {fw.get('version', '')}".rstrip(),
        f"Source:    {meta.get('source', '?')}",
        f"Generated: {meta.get('generated_at', '?')}",
        "",
        "Totals:",
    ]
    for k, v in summary["totals"].items():
        suffix = ""
        if k == "gap_custom_rules" and v > 0:
            suffix = "  (count of custom rules — process-checks etc.; not a deliverable gap)"
        lines.append(f"  {k}: {v}{suffix}")
    lines.append("")
    lines.append("Severity:")
    for k, v in summary["severity_histogram"].items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Source type:")
    for k, v in summary["source_type_histogram"].items():
        lines.append(f"  {k}: {v}")
    lines.append("")
    lines.append("Service breakdown (top 10):")
    for k, v in list(summary["service_breakdown"].items())[:10]:
        lines.append(f"  {k}: {v}")
    lines.append("")
    if is_ready(summary):
        lines.append("Status: READY (0 todos, 0 unset severity)")
    else:
        t = summary["totals"]
        lines.append(
            f"Status: NOT READY ({t['total_todo_placeholders']} todos in "
            f"{t['rules_with_todos']} rules; {t['gap_unset_severity']} unset severity)"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=pathlib.Path)
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="exit non-zero when status is NOT READY (CI/handoff gate)",
    )
    args = parser.parse_args()

    doc = yaml.safe_load(args.file.read_text(encoding="utf-8"))
    summary = summarize(doc)
    summary["ready"] = is_ready(summary)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(render_text(summary))
    if args.strict and not summary["ready"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
