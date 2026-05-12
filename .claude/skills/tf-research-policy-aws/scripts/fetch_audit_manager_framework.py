#!/usr/bin/env python3
"""Fetch all controls in an AWS Audit Manager standard framework via the AWS API.

Useful for frameworks Security Hub doesn't carry as standards (HIPAA, GDPR,
FedRAMP Moderate, GxP, FERPA, etc.). Audit Manager's standard frameworks
encode the full control catalog with rich per-control metadata.

Prerequisites:
  * boto3 installed (`pip install boto3`)
  * AWS credentials configured
  * Audit Manager enabled in the target account/region

Usage:
  scripts/fetch_audit_manager_framework.py --list-frameworks
  scripts/fetch_audit_manager_framework.py --framework "HIPAA" --output hipaa.json
  scripts/fetch_audit_manager_framework.py --framework-id <uuid> --output out.json

Output schema:
  {
    "framework": {"id": "...", "name": "...", "description": "...", "compliance_type": "..."},
    "fetched_at": "<iso>",
    "controls": [
      {
        "id": "...",
        "name": "...",
        "description": "...",
        "testing_information": "...",
        "action_plan_title": "...",
        "action_plan_instructions": "...",
        "control_sources": "...",
        "tags": {...}
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


def list_frameworks(client: Any) -> list[dict[str, Any]]:
    """List all standard Audit Manager frameworks.

    boto3's list_assessment_frameworks is not always registered as paginatable,
    so we drive nextToken manually rather than trusting get_paginator. The API
    caps page size at 100; loop until nextToken is absent.
    """
    frameworks: list[dict[str, Any]] = []
    next_token: str | None = None
    while True:
        kwargs: dict[str, Any] = {"frameworkType": "Standard", "maxResults": 100}
        if next_token:
            kwargs["nextToken"] = next_token
        resp = client.list_assessment_frameworks(**kwargs)
        frameworks.extend(resp.get("frameworkMetadataList", []))
        next_token = resp.get("nextToken")
        if not next_token:
            break
    return frameworks


def find_framework(client: Any, *, name: str | None, framework_id: str | None) -> dict[str, Any]:
    frameworks = list_frameworks(client)
    if framework_id:
        for f in frameworks:
            if f.get("id") == framework_id:
                return f
        raise SystemExit(f"no framework found with id {framework_id}")
    if name:
        wanted = name.lower()
        matches = [f for f in frameworks if wanted in f.get("name", "").lower()]
        if not matches:
            raise SystemExit(f"no framework matched '{name}'. Use --list-frameworks to see options.")
        if len(matches) > 1:
            names = ", ".join(f["name"] for f in matches)
            raise SystemExit(f"name '{name}' matched multiple frameworks: {names}")
        return matches[0]
    raise SystemExit("must supply --framework or --framework-id")


def fetch_framework_detail(client: Any, framework_id: str) -> dict[str, Any]:
    return client.get_assessment_framework(frameworkId=framework_id)["framework"]


def fetch_control_detail(client: Any, control_id: str) -> dict[str, Any]:
    return client.get_control(controlId=control_id)["control"]


def normalize_control(c: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": c.get("id"),
        "name": c.get("name"),
        "description": c.get("description"),
        "testing_information": c.get("testingInformation"),
        "action_plan_title": c.get("actionPlanTitle"),
        "action_plan_instructions": c.get("actionPlanInstructions"),
        "control_sources": c.get("controlSources"),
        "tags": c.get("tags") or {},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list-frameworks", action="store_true")
    parser.add_argument("--framework", help="framework name (substring, case-insensitive)")
    parser.add_argument("--framework-id", help="explicit framework UUID")
    parser.add_argument("--region")
    parser.add_argument("--profile")
    parser.add_argument("--output", type=pathlib.Path)
    parser.add_argument(
        "--shallow",
        action="store_true",
        help="skip per-control get_control calls (faster, less detail)",
    )
    args = parser.parse_args()

    session = boto3.Session(region_name=args.region, profile_name=args.profile)
    client = session.client("auditmanager")

    try:
        if args.list_frameworks:
            frameworks = list_frameworks(client)
            json.dump(frameworks, sys.stdout, indent=2, default=str)
            sys.stdout.write("\n")
            return 0

        meta = find_framework(client, name=args.framework, framework_id=args.framework_id)
        framework = fetch_framework_detail(client, meta["id"])
    except (BotoCoreError, ClientError) as exc:
        print(f"AWS API error: {exc}", file=sys.stderr)
        return 2

    controls: list[dict[str, Any]] = []
    for control_set in framework.get("controlSets", []):
        for c in control_set.get("controls", []):
            if args.shallow:
                controls.append(normalize_control(c))
            else:
                try:
                    detail = fetch_control_detail(client, c["id"])
                    controls.append(normalize_control(detail))
                except (BotoCoreError, ClientError) as exc:
                    print(f"warn: get_control({c['id']}) failed: {exc}", file=sys.stderr)
                    controls.append(normalize_control(c))

    mode = "shallow" if args.shallow else "deep"
    out = {
        "framework": {
            "id": framework.get("id"),
            "name": framework.get("name"),
            "description": framework.get("description"),
            "compliance_type": framework.get("complianceType"),
            "mode": mode,
        },
        "fetched_at": _dt.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "controls": controls,
    }
    text = json.dumps(out, indent=2, default=str)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"wrote {len(controls)} controls ({mode}) to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
