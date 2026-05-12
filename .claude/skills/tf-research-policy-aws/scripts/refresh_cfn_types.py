#!/usr/bin/env python3
"""Refresh references/cfn-resource-types.txt from the public CFN Resource Specification.

The CloudFormation Resource Specification is a single JSON document that AWS
keeps current as new resource types ship. We snapshot the list of type names
so `validate_yaml.py` can check `resource_types[]` entries offline without
needing to fetch the full spec on every run.

Usage:
    scripts/refresh_cfn_types.py [--output PATH]
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import sys
import urllib.request

SPEC_URL = "https://d1uauaxba7bl26.cloudfront.net/latest/CloudFormationResourceSpecification.json"
DEFAULT_OUTPUT = (
    pathlib.Path(__file__).resolve().parent.parent / "references" / "cfn-resource-types.txt"
)


def fetch_spec(url: str = SPEC_URL) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "tf-research-policy-aws/1"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_types(spec: dict) -> list[str]:
    """Pull resource type names from the CFN spec, sorted.

    The spec is a single JSON document with a `ResourceTypes` map at the top
    level; the keys are the type names we care about. If AWS renames the
    top-level key (or the doc is malformed), return [] — the caller decides
    whether the empty list is fatal.
    """
    return sorted((spec or {}).get("ResourceTypes", {}).keys())


def write_snapshot(path: pathlib.Path, types: list[str]) -> None:
    today = _dt.date.today().isoformat()
    header = (
        "# CloudFormation Resource Specification snapshot\n"
        f"# Source: {SPEC_URL}\n"
        f"# Refreshed: {today}\n"
        "# Format: one CFN resource type per line\n"
        "# Refresh with: scripts/refresh_cfn_types.py --output references/cfn-resource-types.txt\n"
    )
    path.write_text(header + "\n".join(types) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--url", default=SPEC_URL)
    args = parser.parse_args()
    spec = fetch_spec(args.url)
    types = extract_types(spec)
    if len(types) < 500:
        print(f"refused to write: only {len(types)} types parsed; spec format may have changed",
              file=sys.stderr)
        return 2
    write_snapshot(args.output, types)
    print(f"wrote {len(types)} CFN types to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
