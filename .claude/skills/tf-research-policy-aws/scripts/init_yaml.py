#!/usr/bin/env python3
"""Emit a tf-research-policy-aws YAML scaffold with the metadata block populated.

Usage:
  scripts/init_yaml.py --framework "CIS AWS Foundations Benchmark" --version "3.0.0" \
      --source https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html \
      --output policy-research/cis-aws-foundations-3.0.0.yaml
"""
from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import sys

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--framework", required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--source", required=True, help="primary AWS doc URL")
    parser.add_argument("--scope", help="optional scope, e.g., 'S3 only'")
    parser.add_argument("--output", type=pathlib.Path, help="default: stdout")
    parser.add_argument("--notes", help="free-form notes for the metadata block")
    args = parser.parse_args()

    framework: dict = {"name": args.framework, "version": args.version}
    if args.scope:
        framework["scope"] = args.scope

    doc = {
        "metadata": {
            "framework": framework,
            "source": args.source,
            "generated_by": "tf-research-policy-aws",
            "generated_at": _dt.date.today().isoformat(),
            **({"notes": args.notes} if args.notes else {}),
        },
        "rules": [],
    }
    out = yaml.safe_dump(doc, sort_keys=False, width=100, default_flow_style=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        print(f"wrote scaffold to {args.output}", file=sys.stderr)
    else:
        sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
