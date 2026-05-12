#!/usr/bin/env python3
"""Parse an AWS Config Conformance Pack CFN template into a YAML rule skeleton.

Conformance pack templates are CloudFormation YAML or JSON. They encode a
mapping from framework controls to AWS Config managed rules — exactly the
data we want as the seed for our rule YAML. This script extracts everything
that's deterministically present in the template and emits a YAML skeleton
for the model to enrich with verbatim requirement text, severity, remediation,
and test cases.

Usage:
    scripts/parse_conformance_pack.py <url-or-path> --framework "<name>" --version "<v>" [--output PATH]

The skeleton is written to stdout if --output is omitted.
"""
from __future__ import annotations

import argparse
import copy
import datetime as _dt
import json
import pathlib
import re
import sys
from typing import Any

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    REFERENCES,
    CfnLoader,
    http_get,
    kebab,
    load_json_remap,
    safe_dump_yaml,
)

LEGACY_IDENTIFIER_REMAP = load_json_remap(REFERENCES / "legacy-identifier-remap.json")
LEGACY_CFN_TYPE_REMAP = load_json_remap(REFERENCES / "legacy-cfn-type-remap.json")

# Identifiers AWS Config publishes as managed rules but that aren't strictly
# "evaluate this resource" — `AWS_CONFIG_PROCESS_CHECK` is a manual attestation
# placeholder. Conformance packs include it for procedural controls. We flip the
# source.type so the validator's managed-rules check doesn't reject it.
PROCESS_CHECK_IDENTIFIERS: set[str] = {"AWS_CONFIG_PROCESS_CHECK"}


def fetch(source: str) -> str:
    """Read a file from a URL or path."""
    if re.match(r"^https?://", source):
        return http_get(source)
    return pathlib.Path(source).read_text(encoding="utf-8")


def parse_template(text: str) -> dict[str, Any]:
    """Parse YAML or JSON CFN template."""
    text = text.lstrip()
    if text.startswith("{"):
        return json.loads(text)
    return yaml.load(text, Loader=CfnLoader)


def _remap_identifier(identifier: str | None) -> tuple[str | None, bool]:
    """Return (canonical_identifier, is_process_check). Idempotent — pass through if unchanged."""
    if not identifier:
        return identifier, False
    if identifier in PROCESS_CHECK_IDENTIFIERS:
        return identifier, True
    return LEGACY_IDENTIFIER_REMAP.get(identifier, identifier), False


def _remap_cfn_type(rt: str) -> str:
    return LEGACY_CFN_TYPE_REMAP.get(rt, rt)


def extract_rules(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull every AWS::Config::ConfigRule out of the template's Resources block."""
    rules = []
    resources = template.get("Resources") or {}
    for logical_id, body in resources.items():
        if not isinstance(body, dict):
            continue
        if body.get("Type") != "AWS::Config::ConfigRule":
            continue
        props = body.get("Properties") or {}
        source = props.get("Source") or {}
        scope = props.get("Scope") or {}
        rules.append(
            {
                "logical_id": logical_id,
                "config_rule_name": props.get("ConfigRuleName") or kebab(logical_id),
                "description": (props.get("Description") or "").strip(),
                "source_owner": source.get("Owner"),
                "source_identifier": source.get("SourceIdentifier"),
                "input_parameters": props.get("InputParameters") or {},
                "compliance_resource_types": scope.get("ComplianceResourceTypes") or [],
            }
        )
    return rules


def service_slug(resource_types: list[str]) -> str | None:
    """Best-effort service slug from CFN resource type (AWS::S3::Bucket -> s3)."""
    for rt in resource_types:
        parts = rt.split("::")
        if len(parts) >= 2:
            return parts[1].lower()
    return None


def to_skeleton_rule(parsed: dict[str, Any]) -> dict[str, Any]:
    """Map parsed conformance pack rule into the skill's YAML schema (skeleton).

    Provenance attribution:
      * Fields populated verbatim from the conformance pack (source.identifier,
        source.parameters, condition.parameters, resource_types) get
        `aws-conformance-pack`.
      * source.documentation_url and references[0].url are *constructed* by the
        parser from the canonical Config rule slug — they point at the AWS Config
        developer guide page, not at the conformance pack template. They get
        `aws-config-managed-rule-doc` so an auditor can tell where the URL came from.
    """
    raw_identifier = parsed["source_identifier"]
    canonical_identifier, is_process_check = _remap_identifier(raw_identifier)
    is_managed = parsed["source_owner"] == "AWS" and not is_process_check
    resource_types = [_remap_cfn_type(rt) for rt in parsed["compliance_resource_types"]]
    canonical_kebab = (canonical_identifier or "").replace("_", "-").lower()
    rule_slug = canonical_kebab or parsed["config_rule_name"]

    # Provenance: distinguish "from the pack" from "constructed by the parser
    # against the developer guide". The developer-guide URL is not in the pack.
    provenance: dict[str, Any] = {
        "source.identifier": "aws-conformance-pack",
        "framework_control.id": "aws-conformance-pack",
    }
    if parsed["compliance_resource_types"]:
        provenance["resource_types"] = "aws-conformance-pack"
    if parsed["input_parameters"]:
        provenance["source.parameters"] = "aws-conformance-pack"
        provenance["condition.parameters"] = "aws-conformance-pack"
    if is_managed:
        # Constructed URL pointing at the AWS Config developer guide page.
        provenance["source.documentation_url"] = "aws-config-managed-rule-doc"
        provenance["references"] = ["aws-config-managed-rule-doc"]

    return {
        "id": parsed["config_rule_name"],
        "title": "TODO: imperative title from controls reference page",
        "framework_control": {
            "id": "TODO: framework control ID (e.g., CIS 2.3.1)",
            "title": "TODO: control title from framework",
            "requirement": "TODO: verbatim requirement text from controls reference page",
        },
        "severity": "TODO: CRITICAL|HIGH|MEDIUM|LOW from Security Hub control page",
        "service": service_slug(resource_types) or "TODO: aws service slug",
        "resource_types": resource_types or ["TODO: AWS::Service::Resource"],
        "source": {
            "type": "aws-config-managed-rule" if is_managed else "aws-config-custom-rule",
            "identifier": canonical_identifier or raw_identifier or "TODO: identifier",
            "documentation_url": (
                f"https://docs.aws.amazon.com/config/latest/developerguide/{rule_slug}.html"
                if is_managed
                else "TODO: custom rule documentation URL"
            ),
            "parameters": parsed["input_parameters"],
        },
        "condition": {
            "description": parsed["description"]
            or "TODO: plain-English description of compliant state",
            "parameters": copy.deepcopy(parsed["input_parameters"]),
            "logic": "TODO: pseudocode or property expression",
        },
        "remediation": {
            "summary": "TODO: how a consumer fixes a non-compliant resource",
            "terraform_snippet": "TODO: minimal compliant HCL",
        },
        "references": [
            {
                "title": f"AWS Config managed rule {rule_slug}",
                "url": f"https://docs.aws.amazon.com/config/latest/developerguide/{rule_slug}.html",
            }
        ],
        "test_cases": [
            {
                "name": "TODO: compliant case",
                "input": {"resource_type": "TODO", "properties": {}},
                "expected": "COMPLIANT",
            }
        ],
        "tags": [],
        "provenance": provenance,
    }


def build_document(
    template: dict[str, Any],
    framework: str,
    version: str,
    source_url: str,
    notes: str | None = None,
) -> dict[str, Any]:
    rules = extract_rules(template)
    return {
        "metadata": {
            "framework": {"name": framework, "version": version},
            "source": source_url,
            "generated_by": "tf-research-policy-aws",
            "generated_at": _dt.date.today().isoformat(),
            "notes": notes or (
                "Skeleton produced from an AWS Config conformance pack. "
                "Phase 4 (bulk_enrich.py) populates the remaining fields "
                "from references/managed-rules-metadata.json."
            ),
        },
        "rules": [to_skeleton_rule(r) for r in rules],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="URL or path to conformance pack CFN template")
    parser.add_argument("--framework", required=True, help="Framework name, e.g., 'CIS AWS Foundations Benchmark'")
    parser.add_argument("--version", required=True, help="Framework version, e.g., '3.0.0'")
    parser.add_argument("--output", type=pathlib.Path, help="Write to this file (default: stdout)")
    parser.add_argument("--source-url", help="Override the metadata.source URL (default: --source)")
    parser.add_argument(
        "--notes",
        help=(
            "Custom metadata.notes string. Use this when the conformance pack is a "
            "documented substitute for the requested framework (e.g., CIS v1.4 L1 "
            "in place of CIS v3.0.0, or the Security/Identity/Compliance pack in "
            "place of FSBP). Without --notes the file uses a generic default."
        ),
    )
    args = parser.parse_args()

    text = fetch(args.source)
    template = parse_template(text)
    source_url = args.source_url or (
        args.source if re.match(r"^https?://", args.source) else f"file://{pathlib.Path(args.source).resolve()}"
    )
    doc = build_document(template, args.framework, args.version, source_url, notes=args.notes)

    if args.output:
        safe_dump_yaml(doc, args.output)
        print(f"wrote {len(doc['rules'])} rule skeletons to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(safe_dump_yaml(doc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
