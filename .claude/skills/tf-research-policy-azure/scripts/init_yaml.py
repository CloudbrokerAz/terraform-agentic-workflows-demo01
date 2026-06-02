#!/usr/bin/env python3
"""Create an empty tf-research-policy-azure YAML scaffold (metadata + []).

Use for single-control or no-initiative runs; add rule entries by hand (set
source.policy_definition_name to the built-in GUID) and let bulk_enrich.py
fill the rest from the snapshot.
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys

from _common import dump_yaml


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--framework", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--source", required=True, help="primary MS doc URL")
    ap.add_argument("--scope", default="")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    fw: dict = {"name": args.framework, "version": args.version}
    if args.scope:
        fw["scope"] = args.scope
    doc = {
        "metadata": {
            "framework": fw,
            "source": args.source,
            "generated_by": "tf-research-policy-azure",
            "generated_at": dt.datetime.now(dt.timezone.utc)
            .date().isoformat(),
        },
        "rules": [],
    }
    dump_yaml(doc, args.output)
    print(f"Wrote scaffold: {args.output}")
    print("Next: add rule entries (source.policy_definition_name = built-in "
          "GUID), then `bulk_enrich.py --yaml <file> --require-zero-todos`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
