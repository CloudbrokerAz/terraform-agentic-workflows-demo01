#!/usr/bin/env python3
"""Build (or refresh) references/policy-def-guid-index.json — the bundled
GUID -> repo-path index used by bulk_enrich.py and parse_builtin_initiative.py
when `az` is unavailable. One pass over Azure/azure-policy@master via the
public GitHub tree + raw endpoints; no Azure auth required.

Output index covers both built-in policy DEFINITIONS and built-in policy SET
definitions (initiatives), keyed by GUID. Run periodically (Microsoft ships
policies weekly); re-run is safe and additive.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from _common import REF

TREE_URL = ("https://api.github.com/repos/Azure/azure-policy/git/trees/"
            "master?recursive=1")
RAW_PREFIX = "https://raw.githubusercontent.com/Azure/azure-policy/master/"
INDEX_PATH = os.path.join(REF, "policy-def-guid-index.json")


def fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={
        "User-Agent": "tf-research-policy-azure/build_policy_index",
        "Accept": "application/json",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310
        return r.read()


def extract_name(path: str) -> tuple[str, str, str] | None:
    """Return (kind, guid, path) for one repo file. kind in {def,set}."""
    raw_url = RAW_PREFIX + path.replace(" ", "%20")
    try:
        d = json.loads(fetch(raw_url))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write(f"  skip {path}: {exc}\n")
        return None
    name = d.get("name")
    if not isinstance(name, str) or len(name) < 30:
        return None
    kind = ("set" if "/policySetDefinitions/" in path else "def")
    return (kind, name, path)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=50,
                    help="parallel fetch workers (default 50)")
    ap.add_argument("--out", default=INDEX_PATH)
    args = ap.parse_args()

    print(f"Reading tree from {TREE_URL}")
    tree = json.loads(fetch(TREE_URL))
    if tree.get("truncated"):
        sys.stderr.write("WARNING: tree truncated — index will be partial\n")
    blobs = [e for e in tree["tree"] if e["type"] == "blob"]
    targets = [e["path"] for e in blobs
               if e["path"].startswith("built-in-policies/policyDefinitions/")
               or e["path"].startswith(
                   "built-in-policies/policySetDefinitions/")
               if e["path"].endswith(".json")]
    print(f"Found {len(targets)} candidate files. Fetching with "
          f"{args.workers} workers...")

    defs: dict[str, str] = {}
    sets: dict[str, str] = {}
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(extract_name, p): p for p in targets}
        for f in as_completed(futures):
            done += 1
            if done % 250 == 0:
                print(f"  {done}/{len(targets)}")
            res = f.result()
            if not res:
                continue
            kind, guid, path = res
            (sets if kind == "set" else defs)[guid] = path

    index = {
        "_comment": ("GUID -> repo-path index for built-in policy "
                      "definitions and initiatives in Azure/azure-policy@"
                      "master. Used by bulk_enrich.py and "
                      "parse_builtin_initiative.py when `az` is unavailable. "
                      "Refresh with build_policy_index.py."),
        "generated_at": dt.datetime.now(dt.timezone.utc).date().isoformat(),
        "source_repo": "Azure/azure-policy@master",
        "raw_url_prefix": RAW_PREFIX,
        "definitions": dict(sorted(defs.items())),
        "initiatives": dict(sorted(sets.items())),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2)
        fh.write("\n")
    print(f"\nWrote {args.out}")
    print(f"  definitions: {len(defs)}")
    print(f"  initiatives: {len(sets)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
