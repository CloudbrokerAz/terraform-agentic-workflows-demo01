#!/usr/bin/env python3
"""Merge AWS CloudFormation Guard Rules Registry test fixtures into a YAML rule set.

The AWS Guard Rules Registry (aws-cloudformation/aws-guard-rules-registry,
Apache-2.0) ships paired Guard rule files and CloudFormation test fixtures.
The fixtures are exactly the COMPLIANT/NON_COMPLIANT pairs we want as
`test_cases[]` in the policy YAML.

Each framework has a `mappings/rule_set_<framework>.json` file mapping
guardFilePath -> controls[]. Each guard file has a paired test fixture under
`<dir>/tests/<basename>_tests.yml` with PASS/FAIL/SKIP expectations against
real CFN snippets.

This script fetches the mapping for a chosen framework, walks each guard
rule, locates the matching test fixture, and either:
  - Emits a JSON file keyed by control ID -> {rule_identifier, test_cases[]}
    (--mode emit)
  - Merges directly into a YAML rule set, populating test_cases[] for any
    rule whose framework_control.id matches a control in the mapping
    (--mode merge --yaml <path>)

Usage:
  scripts/fetch_guard_registry.py --list-frameworks
  scripts/fetch_guard_registry.py --framework cis_aws_benchmark_level_1 \
       --mode merge --yaml policy-research/cis-3.0.yaml
  scripts/fetch_guard_registry.py --framework cmmc_level_2 \
       --mode emit --output /tmp/cmmc-guard.json
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.parse
import urllib.request
from typing import Any

import yaml

REPO = "aws-cloudformation/aws-guard-rules-registry"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
API_BASE = f"https://api.github.com/repos/{REPO}"

PASS_FAIL_TO_EXPECTED = {"PASS": "COMPLIANT", "FAIL": "NON_COMPLIANT"}


def _cfn_constructor(loader: yaml.SafeLoader, tag_suffix: str, node: yaml.Node) -> Any:
    """Render CloudFormation intrinsic functions (!Ref, !If, !Sub, ...) as plain dicts."""
    name = "Fn::" + tag_suffix if tag_suffix != "Ref" else "Ref"
    if isinstance(node, yaml.ScalarNode):
        return {name: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {name: loader.construct_sequence(node)}
    return {name: loader.construct_mapping(node)}


class CfnLoader(yaml.SafeLoader):
    pass


CfnLoader.add_multi_constructor("!", _cfn_constructor)
CfnLoader.add_multi_constructor("tag:yaml.org,2002:!", _cfn_constructor)


def http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tf-research-policy-aws/1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def list_frameworks() -> list[str]:
    contents = json.loads(http_get(f"{API_BASE}/contents/mappings?ref={BRANCH}"))
    out = []
    for item in contents:
        name = item.get("name") or ""
        if name.startswith("rule_set_") and name.endswith(".json"):
            out.append(name[len("rule_set_") : -len(".json")])
    return sorted(out)


def fetch_mapping(framework: str) -> dict[str, Any]:
    return json.loads(http_get(f"{RAW_BASE}/mappings/rule_set_{framework}.json"))


def fetch_text_or_none(url: str) -> str | None:
    try:
        return http_get(url)
    except urllib.error.HTTPError:
        return None


def parse_rule_identifier(guard_text: str) -> str | None:
    m = re.search(
        r"^#\s*Rule Identifier:\s*\n#\s*(\S+)",
        guard_text,
        flags=re.MULTILINE,
    )
    return m.group(1) if m else None


def parse_resource_types(guard_text: str) -> list[str]:
    m = re.search(r"^#\s*Reports on:\s*\n((?:#\s+\S.*\n)+)", guard_text, flags=re.MULTILINE)
    if not m:
        return []
    block = m.group(1)
    types: list[str] = []
    for line in block.splitlines():
        line = line.lstrip("# ").strip()
        if line.startswith("AWS::"):
            types.append(line)
    return types


def test_fixture_path(guard_path: str) -> str:
    """rules/aws/svc/foo.guard -> rules/aws/svc/tests/foo_tests.yml"""
    p = pathlib.PurePosixPath(guard_path)
    return str(p.parent / "tests" / (p.stem + "_tests.yml"))


def extract_test_cases(fixture_yaml: str, rule_identifier: str | None) -> list[dict[str, Any]]:
    try:
        cases = yaml.load(fixture_yaml, Loader=CfnLoader) or []
    except yaml.YAMLError:
        return []
    out: list[dict[str, Any]] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        rules = (case.get("expectations") or {}).get("rules") or {}
        # If we know the rule identifier, use its expectation; else union of any.
        if rule_identifier and rule_identifier in rules:
            outcome = rules[rule_identifier]
        elif rules:
            outcome = next(iter(rules.values()))
        else:
            continue
        expected = PASS_FAIL_TO_EXPECTED.get(str(outcome).upper())
        if not expected:
            continue  # SKIP cases aren't useful as policy unit tests
        out.append(
            {
                "name": case.get("name") or "Guard registry test",
                "input": case.get("input") or {},
                "expected": expected,
            }
        )
    return out


def collect_per_control(
    mapping: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Walk the framework mapping, fetch guard + tests.

    Returns two indexes:
      * per_control[control_id]   — aggregated across all guard rules under that control
      * per_rule[rule_identifier] — the SPECIFIC guard rule with that identifier
    """
    per_control: dict[str, dict[str, Any]] = {}
    per_rule: dict[str, dict[str, Any]] = {}
    fetched_guard: dict[str, dict[str, Any]] = {}

    for entry in mapping.get("mappings") or []:
        guard_path = entry.get("guardFilePath")
        if not guard_path:
            continue
        if guard_path not in fetched_guard:
            guard_text = fetch_text_or_none(f"{RAW_BASE}/{guard_path}")
            fixture_text = fetch_text_or_none(f"{RAW_BASE}/{test_fixture_path(guard_path)}")
            rule_identifier = parse_rule_identifier(guard_text or "") if guard_text else None
            resource_types = parse_resource_types(guard_text or "") if guard_text else []
            test_cases = (
                extract_test_cases(fixture_text, rule_identifier) if fixture_text else []
            )
            fetched_guard[guard_path] = {
                "rule_identifier": rule_identifier,
                "resource_types": resource_types,
                "test_cases": test_cases,
                "guard_path": guard_path,
            }
        info = fetched_guard[guard_path]
        controls = entry.get("controls") or []

        # Per-rule index: specific to this guard rule
        if info["rule_identifier"]:
            per_rule.setdefault(
                info["rule_identifier"],
                {
                    "controls": [],
                    "resource_types": list(info["resource_types"]),
                    "test_cases": list(info["test_cases"]),
                    "guard_paths": [info["guard_path"]],
                },
            )
            for c in controls:
                if c not in per_rule[info["rule_identifier"]]["controls"]:
                    per_rule[info["rule_identifier"]]["controls"].append(c)

        # Per-control index: aggregated across guard rules
        for control in controls:
            agg = per_control.setdefault(
                control,
                {"rule_identifiers": [], "resource_types": [], "test_cases": [], "guard_paths": []},
            )
            if info["rule_identifier"] and info["rule_identifier"] not in agg["rule_identifiers"]:
                agg["rule_identifiers"].append(info["rule_identifier"])
            for rt in info["resource_types"]:
                if rt not in agg["resource_types"]:
                    agg["resource_types"].append(rt)
            agg["test_cases"].extend(info["test_cases"])
            if guard_path not in agg["guard_paths"]:
                agg["guard_paths"].append(guard_path)
    return per_control, per_rule


def merge_into_yaml(
    yaml_path: pathlib.Path,
    per_control: dict[str, dict[str, Any]],
    per_rule: dict[str, dict[str, Any]],
    force: bool,
) -> int:
    doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    rules = doc.get("rules") or []

    matched = 0
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        info = None

        # Strategy 1 (preferred): match by source.identifier — gives us the
        # specific guard rule's data (test cases, resource types, guard path).
        src_id = str(((rule.get("source") or {}).get("identifier")) or "")
        if src_id in per_rule:
            info = per_rule[src_id]
            # Populate framework_control.id from Guard's mapping if not already set.
            fc = rule.setdefault("framework_control", {})
            if (not fc.get("id") or str(fc.get("id")).startswith("TODO")) and info["controls"]:
                fc["id"] = info["controls"][0]
                rule.setdefault("provenance", {})["framework_control"] = "aws-guard-registry"
                if len(info["controls"]) > 1:
                    related = rule.setdefault("related_controls", [])
                    seen = {(r.get("framework"), r.get("id")) for r in related if isinstance(r, dict)}
                    for other in info["controls"][1:]:
                        if ("Same framework, different control", other) not in seen:
                            related.append({"framework": "Same framework, different control", "id": other})

        # Strategy 2 (fallback): match by framework_control.id — gives us aggregated
        # per-control data (only useful if no source.identifier match was found).
        if info is None:
            ctrl = str(((rule.get("framework_control") or {}).get("id")) or "")
            if ctrl and not ctrl.startswith("TODO") and ctrl in per_control:
                info = per_control[ctrl]

        if not info:
            continue
        matched += 1
        # Replace test_cases if currently empty or all-TODO; else append unique-by-name.
        existing = rule.get("test_cases") or []
        existing_all_todo = all(
            isinstance(tc, dict) and str(tc.get("name", "")).startswith("TODO") for tc in existing
        )
        if existing_all_todo or force:
            rule["test_cases"] = info["test_cases"]
        else:
            seen_names = {str(tc.get("name", "")) for tc in existing if isinstance(tc, dict)}
            for tc in info["test_cases"]:
                if tc["name"] not in seen_names:
                    existing.append(tc)
        # Also add references to the guard rule files
        refs = rule.setdefault("references", [])
        seen_urls = {r.get("url") for r in refs if isinstance(r, dict)}
        for path in info["guard_paths"]:
            url = f"https://github.com/{REPO}/blob/{BRANCH}/{path}"
            if url not in seen_urls:
                refs.append({"title": "AWS Guard rule", "url": url})
                seen_urls.add(url)
        # Record provenance
        provenance = rule.setdefault("provenance", {})
        if info["test_cases"]:
            provenance["test_cases"] = "aws-guard-registry"
        existing_refs_prov = provenance.get("references")
        if isinstance(existing_refs_prov, list):
            if "aws-guard-registry" not in existing_refs_prov:
                existing_refs_prov.append("aws-guard-registry")
        elif existing_refs_prov:
            provenance["references"] = [existing_refs_prov, "aws-guard-registry"]
        else:
            provenance["references"] = ["aws-guard-registry"]
    yaml_path.write_text(
        yaml.safe_dump(doc, sort_keys=False, width=100, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return matched


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-frameworks", action="store_true")
    parser.add_argument("--framework", help="framework id (substring match)")
    parser.add_argument("--mode", choices=["emit", "merge"], default="emit")
    parser.add_argument("--yaml", type=pathlib.Path, help="YAML file to merge into (mode=merge)")
    parser.add_argument("--output", type=pathlib.Path, help="JSON output path (mode=emit)")
    parser.add_argument("--force", action="store_true", help="overwrite existing test_cases on merge")
    args = parser.parse_args()

    if args.list_frameworks:
        for f in list_frameworks():
            print(f)
        return 0

    if not args.framework:
        print("must supply --framework or --list-frameworks", file=sys.stderr)
        return 2

    frameworks = list_frameworks()
    needle = args.framework.lower()
    matches = [f for f in frameworks if needle in f.lower()]
    if not matches:
        print(f"no framework matched '{args.framework}'", file=sys.stderr)
        return 2
    if len(matches) > 1:
        print(f"'{args.framework}' matched: {', '.join(matches)}", file=sys.stderr)
        return 2
    fw = matches[0]

    print(f"fetching mapping for {fw} ...", file=sys.stderr)
    mapping = fetch_mapping(fw)
    n_mappings = len(mapping.get("mappings") or [])
    print(f"resolving {n_mappings} guard files (with paired test fixtures) ...", file=sys.stderr)
    per_control, per_rule = collect_per_control(mapping)
    n_tests = sum(len(v["test_cases"]) for v in per_rule.values())
    print(
        f"collected {n_tests} test cases across {len(per_rule)} guard rules "
        f"({len(per_control)} controls)",
        file=sys.stderr,
    )

    if args.mode == "emit":
        out = {"per_control": per_control, "per_rule": per_rule}
        text = json.dumps(out, indent=2)
        if args.output:
            args.output.write_text(text + "\n", encoding="utf-8")
            print(f"wrote {args.output}", file=sys.stderr)
        else:
            sys.stdout.write(text + "\n")
        return 0

    if not args.yaml:
        print("--yaml is required for mode=merge", file=sys.stderr)
        return 2
    matched = merge_into_yaml(args.yaml, per_control, per_rule, args.force)
    print(f"merged into {matched} rule(s) of {args.yaml}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
