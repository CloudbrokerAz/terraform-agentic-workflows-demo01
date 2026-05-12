#!/usr/bin/env python3
"""Refresh references/managed-rules.txt from the AWS Config managed rules catalog.

This is a maintenance script — run it occasionally to keep the bundled snapshot
current. The skill itself uses the snapshot offline.

Usage:
    scripts/refresh_managed_rules.py [--output PATH]

The script fetches the canonical catalog page, extracts every kebab-case rule
identifier, sorts and deduplicates, and writes the result with a comment header
recording the source URL and refresh date.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import re
import sys
import urllib.request

CATALOG_URL = "https://docs.aws.amazon.com/config/latest/developerguide/managed-rules-by-aws-config.html"
# AWS occasionally toggles the page format between bare slugs (`href="foo.html"`)
# and relative-prefixed slugs (`href="./foo.html"`). Match either; the optional
# `./` prefix is dropped by the capture group, so the parser stays format-agnostic.
LINK_RE = re.compile(r'href="(?:\./)?([a-z0-9][a-z0-9-]*)\.html"')
DEFAULT_OUTPUT = (
    pathlib.Path(__file__).resolve().parent.parent / "references" / "managed-rules.txt"
)


def fetch_catalog(url: str = CATALOG_URL) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "tf-research-policy-aws/1"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_identifiers(html: str) -> list[str]:
    matches = LINK_RE.findall(html)
    skip = {
        "evaluate-config",
        "managed-rules-by-aws-config",
        "managing-rules-by-region-availability",
    }
    return sorted({m for m in matches if m not in skip and "-" in m})


def write_snapshot(path: pathlib.Path, identifiers: list[str]) -> None:
    today = _dt.date.today().isoformat()
    header = (
        "# AWS Config managed rules catalog snapshot\n"
        f"# Source: {CATALOG_URL}\n"
        f"# Refreshed: {today}\n"
        "# Format: one rule identifier per line, kebab-case form (the URL slug)\n"
        "# To convert to SCREAMING_SNAKE_CASE: replace hyphens with underscores and uppercase\n"
        "# Refresh with: scripts/refresh_managed_rules.py --output references/managed-rules.txt\n"
    )
    path.write_text(header + "\n".join(identifiers) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--url", default=CATALOG_URL)
    args = parser.parse_args()

    html = fetch_catalog(args.url)
    identifiers = extract_identifiers(html)
    if len(identifiers) < 100:
        print(
            f"refused to write snapshot: only {len(identifiers)} identifiers parsed; "
            "page format may have changed",
            file=sys.stderr,
        )
        return 2
    write_snapshot(args.output, identifiers)
    print(f"wrote {len(identifiers)} identifiers to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
