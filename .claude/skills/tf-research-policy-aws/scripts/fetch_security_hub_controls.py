#!/usr/bin/env python3
"""Fetch all controls in an AWS Security Hub standard via the AWS API.

Two modes:

* default (subscribed mode): describe-standards + describe-standards-controls.
  Returns the per-account view of the standard, including which controls are
  enabled. Requires Security Hub enabled AND the standard subscribed.

* `--unsubscribed`: list-security-control-definitions. Returns the catalogue
  view of a standard's controls without requiring the account to subscribe.
  Use when Security Hub is not enabled in the target account but you still
  want authoritative control metadata. The catalogue lacks per-account state
  (`current_region_availability`, `control_status`) but is otherwise the same
  shape.

Output is authoritative: severity, control title, description, remediation URL,
and RelatedRequirements (cross-framework mappings) come straight from AWS.

Prerequisites:
  * boto3 installed (`pip install boto3`)
  * AWS credentials configured (env, ~/.aws, or IAM role)
  * default mode: Security Hub enabled and the standard subscribed
  * `--unsubscribed`: just credentials — no Security Hub enablement needed

Usage:
  scripts/fetch_security_hub_controls.py --list-standards
  scripts/fetch_security_hub_controls.py --standard "AWS Foundational Security Best Practices v1.0.0" --output controls.json
  scripts/fetch_security_hub_controls.py --standard-arn arn:aws:securityhub:us-east-1::standards/cis-aws-foundations-benchmark/v/3.0.0 --output cis.json
  # When the account is not subscribed (or Security Hub isn't enabled):
  scripts/fetch_security_hub_controls.py --standard-arn arn:aws:securityhub:us-east-1::standards/pci-dss/v/4.0.1 --unsubscribed --output pci.json

Output schema (JSON):
  {
    "standard": {"name": "...", "arn": "...", "description": "..."},
    "fetched_at": "<iso date>",
    "controls": [
      {
        "control_id": "RDS.3",
        "title": "...",
        "description": "...",
        "severity": "MEDIUM",
        "remediation_url": "...",
        "related_requirements": ["NIST.800-53.r5 SC-28", "PCI DSS v4.0 3.5.1"],
        "current_region_availability": "AVAILABLE"
      },
      ...
    ]
  }
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys
from typing import Any

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    print("boto3 is required. Install with: pip install boto3", file=sys.stderr)
    sys.exit(2)


def list_standards(client: Any) -> list[dict[str, Any]]:
    standards: list[dict[str, Any]] = []
    paginator = client.get_paginator("describe_standards")
    for page in paginator.paginate():
        standards.extend(page.get("Standards", []))
    return standards


def find_standard(client: Any, *, name: str | None, arn: str | None) -> dict[str, Any]:
    standards = list_standards(client)
    if arn:
        for s in standards:
            if s.get("StandardsArn") == arn:
                return s
        raise SystemExit(f"no standard found with ARN {arn}")
    if name:
        wanted = name.lower()
        matches = [s for s in standards if wanted in s.get("Name", "").lower()]
        if not matches:
            raise SystemExit(f"no standard matched '{name}'. Use --list-standards to see options.")
        if len(matches) > 1:
            names = ", ".join(s["Name"] for s in matches)
            raise SystemExit(f"name '{name}' matched multiple standards: {names}")
        return matches[0]
    raise SystemExit("must supply --standard or --standard-arn")


def get_subscription_arn(client: Any, standard_arn: str) -> str:
    """Find the active subscription for a standard, enabling it if necessary."""
    paginator = client.get_paginator("get_enabled_standards")
    for page in paginator.paginate():
        for sub in page.get("StandardsSubscriptions", []):
            if sub.get("StandardsArn") == standard_arn and sub.get("StandardsStatus") == "READY":
                return sub["StandardsSubscriptionArn"]
    raise SystemExit(
        f"standard {standard_arn} is not enabled in this account/region. "
        "Enable it via the Security Hub console or `aws securityhub batch-enable-standards`."
    )


def fetch_controls(client: Any, subscription_arn: str) -> list[dict[str, Any]]:
    controls: list[dict[str, Any]] = []
    paginator = client.get_paginator("describe_standards_controls")
    for page in paginator.paginate(StandardsSubscriptionArn=subscription_arn):
        controls.extend(page.get("Controls", []))
    return controls


def normalize_control(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "control_id": c.get("ControlId"),
        "title": c.get("Title"),
        "description": c.get("Description"),
        "severity": c.get("SeverityRating"),
        "remediation_url": c.get("RemediationUrl"),
        "related_requirements": c.get("RelatedRequirements") or [],
        "current_region_availability": c.get("CurrentRegionAvailability"),
        "control_status": c.get("ControlStatus"),
        "disabled_reason": c.get("DisabledReason"),
    }


def fetch_control_definitions(client: Any, standard_arn: str) -> list[dict[str, Any]]:
    """Catalogue-view controls via list_security_control_definitions.

    Works without the standard being subscribed in this account. Output shape
    is similar to describe_standards_controls but uses different field names —
    we map them onto the same normalized form.
    """
    controls: list[dict[str, Any]] = []
    next_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"StandardsArn": standard_arn, "MaxResults": 100}
        if next_token:
            kwargs["NextToken"] = next_token
        resp = client.list_security_control_definitions(**kwargs)
        controls.extend(resp.get("SecurityControlDefinitions", []))
        next_token = resp.get("NextToken")
        if not next_token:
            break
    return controls


def normalize_control_definition(c: dict[str, Any]) -> dict[str, Any]:
    """Normalize a SecurityControlDefinition into the same shape as a Standards Control."""
    return {
        "control_id": c.get("SecurityControlId"),
        "title": c.get("Title"),
        "description": c.get("Description"),
        "severity": c.get("SeverityRating"),
        "remediation_url": c.get("RemediationUrl"),
        "related_requirements": c.get("RelatedRequirements") or [],
        "current_region_availability": c.get("CurrentRegionAvailability"),
        "control_status": None,
        "disabled_reason": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-standards", action="store_true", help="list available standards and exit")
    parser.add_argument("--standard", help="standard name (substring match, case-insensitive)")
    parser.add_argument("--standard-arn", help="explicit standards ARN")
    parser.add_argument("--region", help="AWS region (default: from environment)")
    parser.add_argument("--profile", help="AWS profile (default: from environment)")
    parser.add_argument("--output", type=pathlib.Path, help="write JSON to this file (default: stdout)")
    parser.add_argument(
        "--unsubscribed",
        action="store_true",
        help="use list_security_control_definitions (no Security Hub subscription required). "
             "Requires --standard-arn since name lookup goes through describe_standards.",
    )
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region, profile_name=args.profile)
    client = session.client("securityhub")

    try:
        if args.list_standards:
            standards = list_standards(client)
            json.dump(standards, sys.stdout, indent=2, default=str)
            sys.stdout.write("\n")
            return 0

        if args.unsubscribed:
            if not args.standard_arn:
                raise SystemExit(
                    "--unsubscribed requires --standard-arn (name lookup needs describe_standards "
                    "which requires Security Hub enabled). Standard ARNs follow the pattern "
                    "arn:aws:securityhub:<region>::standards/<slug>/v/<version> — for example "
                    "arn:aws:securityhub:us-east-1::standards/pci-dss/v/4.0.1."
                )
            raw_controls = fetch_control_definitions(client, args.standard_arn)
            normalized = [normalize_control_definition(c) for c in raw_controls]
            standard = {
                "Name": args.standard_arn.rsplit("/standards/", 1)[-1],
                "StandardsArn": args.standard_arn,
                "Description": "Catalogue view via list_security_control_definitions",
            }
        else:
            standard = find_standard(client, name=args.standard, arn=args.standard_arn)
            sub_arn = get_subscription_arn(client, standard["StandardsArn"])
            controls = fetch_controls(client, sub_arn)
            normalized = [normalize_control(c) for c in controls]
    except (BotoCoreError, ClientError) as exc:
        print(f"AWS API error: {exc}", file=sys.stderr)
        return 2

    mode = "unsubscribed" if args.unsubscribed else "subscribed"
    out = {
        "standard": {
            "name": standard.get("Name"),
            "arn": standard.get("StandardsArn"),
            "description": standard.get("Description"),
            "mode": mode,
        },
        "fetched_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "controls": normalized,
    }

    text = json.dumps(out, indent=2, default=str)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(out['controls'])} controls ({mode}) to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
