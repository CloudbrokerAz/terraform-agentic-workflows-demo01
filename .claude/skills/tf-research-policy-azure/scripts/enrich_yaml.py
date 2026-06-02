#!/usr/bin/env python3
"""Merge Defender regulatory-compliance JSON (from fetch_defender_compliance.py)
into a skeleton YAML: fills framework_control.{title,requirement}, the
defender_for_cloud block, and per-field dotted provenance.

Matching strategy: a rule matches a Defender control when the trailing
control id of the rule's `framework_control.id` (or its initiative
group_name) equals the Defender control `id`.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

from _common import dump_yaml, load_yaml

SRC_PROV = {
    "defender-regulatory-compliance": "defender-regulatory-compliance",
}


def trailing_id(text: str) -> str:
    m = re.search(r"(\d+(?:\.\d+)*[A-Za-z]?)\s*$", text or "")
    return m.group(1) if m else (text or "").split()[-1] if text else ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yaml", required=True)
    ap.add_argument("--controls", required=True, help="JSON from fetcher")
    ap.add_argument("--source", default="defender-regulatory-compliance",
                    choices=list(SRC_PROV))
    ap.add_argument("--allow-empty", action="store_true")
    args = ap.parse_args()
    prov_val = SRC_PROV[args.source]

    doc = load_yaml(args.yaml)
    with open(args.controls, encoding="utf-8") as fh:
        cdata = json.load(fh)
    std = cdata.get("standard", "")
    by_id = {str(c["id"]): c for c in cdata.get("controls", [])}

    rules = doc.get("rules", [])
    matched = 0
    for r in rules:
        fc = r.setdefault("framework_control", {})
        gid = trailing_id((r.get("initiative") or {}).get("group_name", ""))
        cid = gid or trailing_id(fc.get("id", ""))
        ctrl = by_id.get(cid)
        if not ctrl:
            continue
        matched += 1
        prov = r.setdefault("provenance", {})
        desc = ctrl.get("description", "").strip()
        if desc:
            if str(fc.get("title", "")).startswith("TODO:"):
                fc["title"] = desc
                prov["framework_control.title"] = prov_val
            if str(fc.get("requirement", "")).startswith("TODO:"):
                fc["requirement"] = desc
                prov["framework_control.requirement"] = prov_val
        assess = ctrl.get("assessments") or []
        r["defender_for_cloud"] = {
            "standard": std,
            "control_id": cid,
            "assessment_id": assess[0]["id"] if assess else None,
            "documentation_url": "https://learn.microsoft.com/azure/"
            "defender-for-cloud/concept-regulatory-compliance",
        }
        prov["defender_for_cloud"] = prov_val
        refs = r.setdefault("references", [])
        refs.append({"title": f"Defender for Cloud — {std} control {cid}",
                     "url": "https://learn.microsoft.com/azure/"
                     "defender-for-cloud/regulatory-compliance-dashboard"})

    total = len(rules)
    pct = (matched / total * 100) if total else 0
    print(f"matched {matched}/{total} rules ({pct:.0f}%)")
    if matched == 0 and not args.allow_empty:
        sys.stderr.write(
            "0 matched. Check the --standard slug and that the rule "
            "framework_control.id / initiative group_name trailing control "
            "ids match the Defender control ids. Use --allow-empty only if "
            "Defender genuinely does not carry this standard.\n")
        return 4
    if pct < 50 and not args.allow_empty:
        sys.stderr.write(
            f"WARNING: only {pct:.0f}% matched (<50%). Sample 3 unmatched "
            "rule ids vs 3 Defender control ids before continuing.\n")
    dump_yaml(doc, args.yaml)
    print(f"Updated {args.yaml}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
