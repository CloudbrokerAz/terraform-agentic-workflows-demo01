#!/usr/bin/env python3
"""Validate a tf-research-policy-aws YAML output against the schema and the AWS Config managed rules catalog.

Checks:
  * The file parses as YAML and has the expected top-level shape (metadata + rules)
  * Each rule has the required fields (id, title, framework_control.requirement, severity, service,
    resource_types, source.{type,identifier,documentation_url}, condition.{description,logic},
    remediation.summary, references, test_cases)
  * Rule IDs are unique within the file
  * `severity` values are in the allowed enum
  * `source.type` values are in the allowed enum
  * `aws-config-managed-rule` source identifiers exist in the bundled managed rules snapshot
  * Each rule has at least one test_case
  * No required field still contains a literal "TODO:" placeholder
  * `condition.logic` is non-trivial (--strict)
  * Snapshot freshness (warn when > 90 days old)
  * `--strict-aws-official` rejects provenance values not in the AWS-official set
  * `--allow-model-synthesis` permits `manual-model-synthesised` under strict mode
  * Every URL in metadata.source and references[].url lives on an AWS-owned domain (--strict-aws-official)

Exit codes:
  0  all rules valid
  1  one or more rules failed validation
  2  file unparseable / structural error

Usage:
  scripts/validate_yaml.py <file>
  scripts/validate_yaml.py <file> --strict     # treat warnings as errors too
  scripts/validate_yaml.py <file> --strict-aws-official
  scripts/validate_yaml.py <file> --strict-aws-official --allow-model-synthesis
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
import urllib.parse
from typing import Any

import yaml

# Allow execution as a script and as a module.
if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REFERENCES,
    is_todo,
    load_text_snapshot,
    screaming_to_kebab,
    snapshot_age_days,
)

VALID_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFORMATIONAL"}
VALID_SOURCE_TYPES = {
    "aws-config-managed-rule",
    "aws-config-custom-rule",
    "security-hub-control",
    "custom-lambda",
}
DEFAULT_SNAPSHOT = REFERENCES / "managed-rules.txt"
DEFAULT_CFN_SNAPSHOT = REFERENCES / "cfn-resource-types.txt"
DEFAULT_PSEUDO_TYPES = REFERENCES / "aws-config-pseudo-types.txt"
DEFAULT_PROVENANCE_CATALOG = REFERENCES / "aws-official-provenance.json"
DEFAULT_DOMAIN_ALLOWLIST = REFERENCES / "aws-domain-allowlist.txt"

CFN_TYPE_RE = re.compile(r"^[A-Z][A-Za-z0-9]*::[A-Z][A-Za-z0-9]*::[A-Z][A-Za-z0-9]*$")
SNAPSHOT_STALE_DAYS = 90

# condition.logic heuristic: must be non-trivial. Reject pure "true"/"false"/<10 chars.
TRIVIAL_LOGIC = {"true", "false", "yes", "no", "tbd", "n/a"}
LOGIC_OPERATOR_RE = re.compile(
    r"(==|!=|>=|<=|>|<|\bin\b|\bnot\s+in\b|\bcontains\b|\band\b|\bor\b|\bnot\b|=>"
    r"|\bsubset_of\b|\bintersects\b|\bmatches\b|\bstarts_with\b|\bfor\b)",
    re.IGNORECASE,
)


def load_provenance_catalog(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    """Load value -> {description, official} mapping from references/aws-official-provenance.json."""
    if not path.exists():
        # Conservative built-in fallback; keeps the validator usable if the file is missing.
        return {
            "aws-security-hub": {"official": True},
            "aws-audit-manager": {"official": True},
            "aws-conformance-pack": {"official": True},
            "aws-config-managed-rule-doc": {"official": True},
            "aws-guard-registry": {"official": True},
            "manual-human": {"official": True},
            "manual": {"official": True},
            "manual-model-synthesised": {"official": False},
            "third-party-prowler": {"official": False},
            "third-party-trivy": {"official": False},
            "unknown": {"official": False},
        }
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw.get("values") or {}


def load_domain_allowlist(path: pathlib.Path) -> list[str]:
    """Each line is a host suffix; URL hosts ending with one match. Empty list disables the check."""
    if not path.exists():
        return []
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.lower())
    return out


def url_on_aws_domain(url: str, allowlist: list[str]) -> bool:
    """True if the URL's host (or host+path-prefix) ends with any allowlist entry."""
    if not allowlist:
        return True
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        return False
    if not parsed.netloc:
        return False
    host = parsed.netloc.lower()
    host_path = host + parsed.path.lower()
    for entry in allowlist:
        if "/" in entry:
            if host_path.startswith(entry):
                return True
        else:
            if host == entry or host.endswith("." + entry):
                return True
    return False


def walk_provenance(prov: Any, prefix: str = "") -> list[tuple[str, Any]]:
    """Yield (dotted_key, value) for every leaf in a provenance block.

    Keys may be plain (`severity`) or dotted (`framework_control.title`), and
    values may be a string or list of strings. Dropping `_`-prefixed metadata.
    """
    out: list[tuple[str, Any]] = []
    if not isinstance(prov, dict):
        return out
    for k, v in prov.items():
        if not isinstance(k, str) or k.startswith("_"):
            continue
        full = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.extend(walk_provenance(v, full))
        else:
            out.append((full, v))
    return out


def collect_non_aws_provenance(
    rule: dict[str, Any],
    catalog: dict[str, dict[str, Any]],
    allow_model_synthesis: bool,
) -> list[tuple[str, str]]:
    """Return [(field, source)] tuples for every provenance value that fails strict mode."""
    out: list[tuple[str, str]] = []
    for field, source in walk_provenance(rule.get("provenance") or {}):
        sources = source if isinstance(source, list) else [source]
        for s in sources:
            if not isinstance(s, str) or not s:
                continue
            entry = catalog.get(s)
            if entry is None:
                out.append((field, s))
                continue
            if entry.get("official"):
                continue
            if s == "manual-model-synthesised" and allow_model_synthesis:
                continue
            out.append((field, s))
    return out


def get(d: Any, *path: str, default: Any = None) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(key)
        if cur is None:
            return default
    return cur


def check_required(rule: dict[str, Any], idx: int) -> list[str]:
    """Return a list of error messages for missing required fields."""
    errors: list[str] = []
    rid = get(rule, "id") or f"<rule #{idx}>"
    required_paths = [
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
    ]
    for path in required_paths:
        value = get(rule, *path)
        if value in (None, "", [], {}):
            errors.append(f"{rid}: missing required field {'.'.join(path)}")
        elif isinstance(value, str) and value.startswith("TODO"):
            errors.append(f"{rid}: field {'.'.join(path)} still has TODO placeholder")
    return errors


def check_condition_logic(rule: dict[str, Any], rid: str) -> list[str]:
    """Heuristic catch for lazy `condition.logic` fills. Returns warnings (caller decides severity)."""
    warnings: list[str] = []
    logic = get(rule, "condition", "logic")
    if not isinstance(logic, str) or is_todo(logic):
        return warnings  # required-field check already complains
    stripped = logic.strip().lower()
    if stripped in TRIVIAL_LOGIC:
        warnings.append(
            f"{rid}: condition.logic '{logic.strip()}' is too trivial (must describe the actual check)"
        )
        return warnings
    if len(stripped) < 10:
        warnings.append(
            f"{rid}: condition.logic is suspiciously short (< 10 chars). "
            "It should describe the property being checked."
        )
    if not LOGIC_OPERATOR_RE.search(logic):
        warnings.append(
            f"{rid}: condition.logic has no comparison/membership operator "
            "(==, !=, >, <, in, contains, AND, OR, ...). "
            "Confirm it actually expresses a check."
        )
    return warnings


def check_rule(
    rule: dict[str, Any],
    idx: int,
    managed_rules: set[str],
    cfn_types: set[str],
    pseudo_types: set[str],
    snapshot_path: pathlib.Path,
) -> list[str]:
    errors: list[str] = []
    errors.extend(check_required(rule, idx))

    rid = get(rule, "id") or f"<rule #{idx}>"

    resource_types = get(rule, "resource_types") or []
    if isinstance(resource_types, list):
        for rt in resource_types:
            if not isinstance(rt, str) or rt.startswith("TODO"):
                continue
            if rt in pseudo_types:
                continue  # accept synthetic AWS Config types verbatim
            if not CFN_TYPE_RE.match(rt):
                errors.append(
                    f"{rid}: resource_type '{rt}' is malformed (expected AWS::Service::Resource form)"
                )
                continue
            if cfn_types and rt not in cfn_types:
                errors.append(
                    f"{rid}: resource_type '{rt}' not in CloudFormation Resource Specification snapshot"
                )

    severity = get(rule, "severity")
    if severity is not None and severity not in VALID_SEVERITIES:
        errors.append(
            f"{rid}: severity '{severity}' is not in {sorted(VALID_SEVERITIES)}"
        )

    source_type = get(rule, "source", "type")
    if source_type is not None and source_type not in VALID_SOURCE_TYPES:
        errors.append(
            f"{rid}: source.type '{source_type}' is not in {sorted(VALID_SOURCE_TYPES)}"
        )

    if source_type == "aws-config-managed-rule":
        identifier = get(rule, "source", "identifier") or ""
        kebab = screaming_to_kebab(identifier)
        if managed_rules and kebab not in managed_rules:
            errors.append(
                f"{rid}: source.identifier '{identifier}' not in managed rules snapshot "
                f"(checked as kebab '{kebab}'). Pick one: "
                f"(a) fix a typo in the identifier; "
                f"(b) set source.type to aws-config-custom-rule; "
                f"(c) refresh the snapshot via scripts/refresh_managed_rules.py "
                f"(snapshot: {snapshot_path.name})."
            )

    test_cases = get(rule, "test_cases")
    if isinstance(test_cases, list):
        if not test_cases:
            errors.append(f"{rid}: test_cases is empty; at least one test case is required")
        for tci, tc in enumerate(test_cases):
            if not isinstance(tc, dict):
                errors.append(f"{rid}: test_cases[{tci}] is not a mapping")
                continue
            if tc.get("expected") not in {"COMPLIANT", "NON_COMPLIANT"}:
                errors.append(
                    f"{rid}: test_cases[{tci}].expected must be COMPLIANT or NON_COMPLIANT"
                )

    return errors


def validate_document(
    doc: Any,
    managed_rules: set[str],
    cfn_types: set[str] | None = None,
    pseudo_types: set[str] | None = None,
    *,
    provenance_catalog: dict[str, dict[str, Any]] | None = None,
    domain_allowlist: list[str] | None = None,
    strict_aws_official: bool = False,
    allow_model_synthesis: bool = False,
    snapshot_path: pathlib.Path = DEFAULT_SNAPSHOT,
    cfn_snapshot_path: pathlib.Path = DEFAULT_CFN_SNAPSHOT,
) -> tuple[list[str], list[str]]:
    cfn_types = cfn_types or set()
    pseudo_types = pseudo_types or set()
    provenance_catalog = provenance_catalog or {}
    domain_allowlist = domain_allowlist or []
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(doc, dict):
        errors.append("top-level document must be a mapping with 'metadata' and 'rules'")
        return errors, warnings

    if "metadata" not in doc:
        errors.append("missing top-level 'metadata' block")
    else:
        meta = doc["metadata"]
        for path in [("framework", "name"), ("framework", "version"), ("source",)]:
            if get(meta, *path) in (None, ""):
                errors.append(f"metadata: missing {'.'.join(path)}")
        if strict_aws_official and domain_allowlist:
            src_url = meta.get("source")
            if isinstance(src_url, str) and src_url and not url_on_aws_domain(src_url, domain_allowlist):
                errors.append(
                    f"metadata.source URL '{src_url}' is not on an AWS-owned domain "
                    "(see references/aws-domain-allowlist.txt)"
                )

    rules = doc.get("rules")
    if not isinstance(rules, list) or not rules:
        errors.append("missing or empty top-level 'rules' list")
        return errors, warnings

    seen_ids: dict[str, int] = {}
    for idx, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"rule #{idx} is not a mapping")
            continue
        rid_val = rule.get("id")
        if isinstance(rid_val, str):
            if rid_val in seen_ids:
                errors.append(f"duplicate rule id '{rid_val}' (rule #{idx} and #{seen_ids[rid_val]})")
            else:
                seen_ids[rid_val] = idx
        errors.extend(
            check_rule(rule, idx, managed_rules, cfn_types, pseudo_types, snapshot_path)
        )
        warnings.extend(check_condition_logic(rule, get(rule, "id") or f"<rule #{idx}>"))
        if strict_aws_official:
            non_official = collect_non_aws_provenance(
                rule, provenance_catalog, allow_model_synthesis
            )
            rid_msg = get(rule, "id") or f"<rule #{idx}>"
            for field, source in non_official:
                if source == "manual-model-synthesised":
                    errors.append(
                        f"{rid_msg}: provenance.{field} = 'manual-model-synthesised' "
                        "is rejected by --strict-aws-official. Pass --allow-model-synthesis "
                        "to permit, or replace with manual-human after a human verifies the "
                        "content against AWS-official sources."
                    )
                else:
                    errors.append(
                        f"{rid_msg}: provenance.{field} = '{source}' is not AWS-official. "
                        "Re-run with an AWS-official source or remove --strict-aws-official."
                    )
            if domain_allowlist:
                refs = rule.get("references") or []
                for ri, ref in enumerate(refs):
                    if not isinstance(ref, dict):
                        continue
                    url = ref.get("url")
                    if isinstance(url, str) and url and not url_on_aws_domain(url, domain_allowlist):
                        errors.append(
                            f"{rid_msg}: references[{ri}].url '{url}' is not on an AWS-owned domain"
                        )
                src_url = get(rule, "source", "documentation_url")
                if (
                    isinstance(src_url, str)
                    and src_url
                    and not is_todo(src_url)
                    and not url_on_aws_domain(src_url, domain_allowlist)
                ):
                    errors.append(
                        f"{rid_msg}: source.documentation_url '{src_url}' is not on an AWS-owned domain"
                    )

    if not managed_rules:
        warnings.append(
            "managed rules snapshot is empty or missing; "
            "aws-config-managed-rule identifiers were not verified"
        )
    if not cfn_types:
        warnings.append(
            "CFN resource types snapshot is empty or missing; "
            "resource_types[] entries were checked only for shape, not membership"
        )

    age = snapshot_age_days(snapshot_path)
    if age is not None and age > SNAPSHOT_STALE_DAYS:
        warnings.append(
            f"managed rules snapshot is {age} days old (> {SNAPSHOT_STALE_DAYS}). "
            "Consider running scripts/refresh_managed_rules.py."
        )
    cfn_age = snapshot_age_days(cfn_snapshot_path)
    if cfn_age is not None and cfn_age > SNAPSHOT_STALE_DAYS:
        warnings.append(
            f"CFN resource types snapshot is {cfn_age} days old (> {SNAPSHOT_STALE_DAYS}). "
            "Consider running scripts/refresh_cfn_types.py."
        )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=pathlib.Path, help="YAML file to validate")
    parser.add_argument(
        "--rules-snapshot",
        type=pathlib.Path,
        default=DEFAULT_SNAPSHOT,
        help="path to managed rules snapshot (default: bundled)",
    )
    parser.add_argument(
        "--cfn-types-snapshot",
        type=pathlib.Path,
        default=DEFAULT_CFN_SNAPSHOT,
        help="path to CFN resource types snapshot (default: bundled)",
    )
    parser.add_argument(
        "--pseudo-types-snapshot",
        type=pathlib.Path,
        default=DEFAULT_PSEUDO_TYPES,
        help="path to AWS Config pseudo-types snapshot (default: bundled)",
    )
    parser.add_argument(
        "--provenance-catalog",
        type=pathlib.Path,
        default=DEFAULT_PROVENANCE_CATALOG,
        help="path to provenance values catalog (default: bundled)",
    )
    parser.add_argument(
        "--domain-allowlist",
        type=pathlib.Path,
        default=DEFAULT_DOMAIN_ALLOWLIST,
        help="path to AWS-owned domain allowlist (default: bundled)",
    )
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    parser.add_argument(
        "--strict-aws-official",
        action="store_true",
        help="fail if any rule has provenance from a non-AWS-official source (e.g., third-party-prowler)",
    )
    parser.add_argument(
        "--allow-model-synthesis",
        action="store_true",
        help="under --strict-aws-official, accept manual-model-synthesised provenance "
             "(model-generated content from training-corpus AWS knowledge)",
    )
    args = parser.parse_args()

    try:
        text = args.file.read_text(encoding="utf-8")
        doc = yaml.safe_load(text)
    except FileNotFoundError:
        print(f"file not found: {args.file}", file=sys.stderr)
        return 2
    except yaml.YAMLError as exc:
        print(f"YAML parse error: {exc}", file=sys.stderr)
        return 2

    managed_rules = load_text_snapshot(args.rules_snapshot)
    cfn_types = load_text_snapshot(args.cfn_types_snapshot)
    pseudo_types = load_text_snapshot(args.pseudo_types_snapshot)
    provenance_catalog = load_provenance_catalog(args.provenance_catalog)
    domain_allowlist = load_domain_allowlist(args.domain_allowlist)

    errors, warnings = validate_document(
        doc,
        managed_rules,
        cfn_types,
        pseudo_types,
        provenance_catalog=provenance_catalog,
        domain_allowlist=domain_allowlist,
        strict_aws_official=args.strict_aws_official,
        allow_model_synthesis=args.allow_model_synthesis,
        snapshot_path=args.rules_snapshot,
        cfn_snapshot_path=args.cfn_types_snapshot,
    )

    for w in warnings:
        print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)

    failed = bool(errors) or (args.strict and bool(warnings))
    if failed:
        print(f"FAIL: {len(errors)} error(s), {len(warnings)} warning(s)", file=sys.stderr)
        return 1
    rule_count = len(doc.get("rules") or [])
    print(f"OK: {rule_count} rule(s) validated, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
