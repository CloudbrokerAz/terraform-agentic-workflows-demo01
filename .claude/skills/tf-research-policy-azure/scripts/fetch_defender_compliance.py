#!/usr/bin/env python3
"""Fetch Microsoft Defender for Cloud regulatory-compliance data via `az rest`.

Emits JSON: { standard, controls: [ {id, description, state,
assessments:[{id,description}] } ] }. Never fabricates: if Defender is not
enabled the API returns an empty value list -> this prints a clear message
and exits non-zero (the caller skips Phase 2b, it does NOT fall back to a
third-party source on this basis).
"""
from __future__ import annotations

import argparse
import json
import sys

from _common import az_rest_get

API = "api-version=2019-01-01-preview"
ARM = "https://management.azure.com"


def list_standards(sub: str) -> list[str]:
    j = az_rest_get(f"{ARM}/subscriptions/{sub}/providers/Microsoft.Security/"
                    f"regulatoryComplianceStandards?{API}")
    return [s["name"] for s in (j or {}).get("value", [])]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--subscription", required=True)
    ap.add_argument("--standard", help="standard slug (per-subscription); "
                    "discover with --list-standards")
    ap.add_argument("--list-standards", action="store_true")
    ap.add_argument("--output")
    ap.add_argument("--max-controls", type=int, default=0,
                    help="cap controls fetched (0 = all)")
    args = ap.parse_args()
    sub = args.subscription

    standards = list_standards(sub)
    if args.list_standards:
        if standards:
            print("Assigned regulatory-compliance standards:")
            for s in standards:
                print(f"  {s}")
        else:
            print("No standards returned. Defender for Cloud is likely not "
                  "initialized in this subscription, OR no resources are in "
                  "scope. This is NOT evidence the framework has no controls "
                  "— use the built-in initiative path (2a) + Learn instead.")
        return 0 if standards else 3

    if not args.standard:
        ap.error("--standard is required (or use --list-standards)")
    if standards and args.standard not in standards:
        sys.stderr.write(
            f"WARNING: '{args.standard}' not in assigned standards "
            f"{standards}. Slugs are per-subscription and inconsistent.\n")

    base = (f"{ARM}/subscriptions/{sub}/providers/Microsoft.Security/"
            f"regulatoryComplianceStandards/{args.standard}")
    cj = az_rest_get(f"{base}/regulatoryComplianceControls?{API}")
    ctrls = (cj or {}).get("value", [])
    if not ctrls:
        print(f"No controls for standard '{args.standard}'. Defender not "
              "enabled / standard not assigned / no in-scope resources. "
              "Skip Phase 2b — do NOT treat this as 'framework empty'.")
        return 3

    out_controls = []
    if args.max_controls:
        ctrls = ctrls[:args.max_controls]
    for c in ctrls:
        cid = c["name"]
        cp = c.get("properties", {})
        aj = az_rest_get(f"{base}/regulatoryComplianceControls/{cid}/"
                         f"regulatoryComplianceAssessments?{API}")
        assessments = [
            {"id": a["name"],
             "description": a.get("properties", {}).get("description", "")}
            for a in (aj or {}).get("value", [])
        ]
        out_controls.append({
            "id": cid,
            "description": cp.get("description", ""),
            "state": cp.get("state", ""),
            "assessments": assessments,
        })

    result = {"standard": args.standard, "controls": out_controls}
    text = json.dumps(result, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"Wrote {len(out_controls)} control(s) -> {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
