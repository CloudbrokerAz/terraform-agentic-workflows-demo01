#!/usr/bin/env python3
"""Regenerate references/sh-control-to-config-rule.json from AWS Security Hub controls reference HTML.

The Security Hub controls reference is split per service. Each per-service page
contains a table of controls, and each control's box typically lists the AWS
Config rule it relies on (in a row labelled "AWS Config rule"). This script
walks every per-service page linked from the controls reference index and
extracts those mappings as a flat `control_id -> kebab-config-rule` JSON.

This replaces the hand-curated crosswalk so unsubscribed-mode `enrich_yaml.py`
matches don't depend on someone manually keeping pace with new controls.

Usage:
  scripts/refresh_sh_control_crosswalk.py
  scripts/refresh_sh_control_crosswalk.py --output references/sh-control-to-config-rule.json
  scripts/refresh_sh_control_crosswalk.py --print-only

Notes:
  * AWS occasionally restructures these HTML pages. The parsing is
    deliberately permissive — it pulls anything that looks like
    'AWS Config rule(s):' followed by a managed-rule slug. If extraction
    rates fall, inspect the per-service HTML manually and update INDEX_URL
    / EXTRACT_RE accordingly.
  * The script is HTML-scraping and therefore best-effort. We sanity-check
    against the bundled managed-rules.txt so a typo or mis-extraction
    won't slip into the crosswalk.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import pathlib
import re
import sys
from typing import Any
from urllib.error import HTTPError

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import REFERENCES, http_get, load_text_snapshot  # noqa: E402

DOC_BASE = "https://docs.aws.amazon.com/securityhub/latest/userguide/"
DEFAULT_OUTPUT = REFERENCES / "sh-control-to-config-rule.json"
DEFAULT_RULES_SNAPSHOT = REFERENCES / "managed-rules.txt"

# AWS removed the unified controls-reference index. Each Security Hub standard
# now has its own page that links per-service `*-controls.html` files. Walk
# every standard page below and union the discovered links — this gives us the
# same coverage the old index gave, plus any standard-specific controls.
STANDARD_INDEX_URLS = (
    "https://docs.aws.amazon.com/securityhub/latest/userguide/fsbp-standard.html",
    "https://docs.aws.amazon.com/securityhub/latest/userguide/cis-aws-foundations-benchmark.html",
    "https://docs.aws.amazon.com/securityhub/latest/userguide/pci-controls.html",
    "https://docs.aws.amazon.com/securityhub/latest/userguide/nist-standard.html",
    "https://docs.aws.amazon.com/securityhub/latest/userguide/securityhub-standards-other.html",
)
# Used in the JSON header for traceability — first URL is the primary anchor.
INDEX_URL = STANDARD_INDEX_URLS[0]

# Per-service controls page link pattern. Examples seen on the AWS docs site:
#   acm-controls.html
#   ./acm-controls.html
#   apigateway-controls.html#apigateway-1  (anchor-suffixed; we strip the anchor)
# AWS toggles between bare and `./`-prefixed hrefs and adds anchor fragments
# on the per-standard pages. Match either, ignoring fragments.
PER_SERVICE_LINK_RE = re.compile(
    r'href="(?:\./)?([a-z0-9][a-z0-9-]*-controls\.html)(?:#[^"]*)?"'
)

# Control ID heading on a per-service page. Examples: "[ACM.1]", "[RDS.3]",
# "[S3.14]", "[EC2.5]", "[Route53.1]", "[ELBV2.3]". The service code can contain
# digits (S3, EC2, ELBV2, Route53 etc.) — without `0-9` in the inner character
# class the regex silently skips ~half of all SH controls.
CONTROL_HEADING_RE = re.compile(r"\[([A-Z][A-Za-z0-9]*\.[0-9]+)\]")

# "AWS Config rule(s)" row that follows a control heading. AWS uses two
# wrappers depending on whether the rule is managed (anchored to the dev-guide
# page) or a Security Hub CSPM custom rule (just inline code). Match both:
#   Format A (managed):  <p><b>AWS Config rule:</b> <a href="...">slug</a></p>
#   Format B (custom):   <p><b>AWS Config rule:</b> <code class="code">slug</code></p>
# Cross-checking against managed-rules.txt downstream filters out Format B
# slugs (Security Hub CSPM custom rules aren't AWS Config managed rules).
CONFIG_RULE_LABEL_RE = re.compile(
    r"AWS\s+Config\s+(?:managed\s+)?rule[s]?\s*[:\.]?\s*"
    r"</?(?:strong|b)>?\s*"  # optional close-bold/strong
    r"(?:<a[^>]*>([a-z0-9][a-z0-9-]*)</a>"  # Format A: anchor
    r"|<code[^>]*>([a-z0-9][a-z0-9-]*)</code>)",  # Format B: code
    re.IGNORECASE | re.DOTALL,
)
# Fallback when the label and the slug are in adjacent cells of a table.
TABLE_CELL_FALLBACK_RE = re.compile(
    r"AWS\s+Config\s+(?:managed\s+)?rule[s]?\s*</td>\s*<td[^>]*>\s*<(?:p|code)[^>]*>([a-z0-9][a-z0-9-]*)</(?:p|code)>",
    re.IGNORECASE | re.DOTALL,
)


def fetch_per_service_links(index_html: str) -> list[str]:
    """Return the set of `*-controls.html` links present on the index page."""
    return sorted(set(PER_SERVICE_LINK_RE.findall(index_html)))


def extract_mappings(html: str) -> dict[str, str]:
    """Walk a per-service page, return {control_id: config_rule_slug}.

    We split the page on each control heading, then look for the AWS Config rule
    line within that control's section. This is more robust than a single global
    regex because per-service pages sometimes mention the same Config rule in
    multiple unrelated places.
    """
    out: dict[str, str] = {}
    headings = list(CONTROL_HEADING_RE.finditer(html))
    for i, m in enumerate(headings):
        control_id = m.group(1)
        start = m.end()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(html)
        section = html[start:end]
        slug = None
        m2 = CONFIG_RULE_LABEL_RE.search(section)
        if m2:
            # Format A (anchor) → group(1); Format B (code) → group(2). Whichever fired.
            slug = m2.group(1) or m2.group(2)
        else:
            m3 = TABLE_CELL_FALLBACK_RE.search(section)
            if m3:
                slug = m3.group(1)
        if slug:
            # Skip obvious false positives (e.g., catch-all <code>none</code>).
            if slug == "none":
                continue
            out[control_id] = slug
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=DEFAULT_OUTPUT,
        help="path to crosswalk JSON (default: bundled)",
    )
    parser.add_argument(
        "--rules-snapshot",
        type=pathlib.Path,
        default=DEFAULT_RULES_SNAPSHOT,
        help="path to managed-rules.txt for sanity-check (default: bundled)",
    )
    parser.add_argument("--print-only", action="store_true", help="print to stdout, do not write")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="for debugging: only process the first N per-service pages",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help=(
            "wholesale-replace the existing crosswalk (default: merge, "
            "preserving curated entries the live docs no longer expose). "
            "Use when you've manually verified that removed controls are "
            "intentional and not just doc-format drift."
        ),
    )
    args = parser.parse_args()

    # Walk every standard page; union the per-service links. Each per-standard
    # page lists the subset of `*-controls.html` files relevant to that standard,
    # so we get full coverage by aggregating across standards.
    all_links: set[str] = set()
    for url in STANDARD_INDEX_URLS:
        print(f"fetching {url}", file=sys.stderr)
        try:
            html = http_get(url)
        except HTTPError as exc:
            print(f"  skip {url}: HTTP {exc.code}", file=sys.stderr)
            continue
        page_links = fetch_per_service_links(html)
        new_count = len(set(page_links) - all_links)
        all_links.update(page_links)
        print(f"  -> {len(page_links)} links ({new_count} new)", file=sys.stderr)
    links = sorted(all_links)
    if args.limit:
        links = links[: args.limit]
    print(f"found {len(links)} unique per-service controls pages", file=sys.stderr)

    managed = load_text_snapshot(args.rules_snapshot)
    if not managed:
        print(
            f"warning: managed-rules snapshot {args.rules_snapshot} is empty; "
            "extracted slugs will not be cross-checked",
            file=sys.stderr,
        )

    mappings: dict[str, str] = {}
    skipped_unknown_slug: dict[str, str] = {}
    for link in links:
        url = DOC_BASE + link
        try:
            html = http_get(url)
        except HTTPError as exc:
            print(f"  skip {link}: HTTP {exc.code}", file=sys.stderr)
            continue
        page_mappings = extract_mappings(html)
        # Cross-check each slug against managed-rules.txt; drop unknowns so a
        # mis-extraction can't silently poison the crosswalk.
        for cid, slug in page_mappings.items():
            if managed and slug not in managed:
                skipped_unknown_slug[cid] = slug
                continue
            mappings[cid] = slug
        print(f"  {link}: extracted {len(page_mappings)}", file=sys.stderr)

    if skipped_unknown_slug:
        print(
            f"  skipped {len(skipped_unknown_slug)} extractions whose slug was not in "
            f"the managed-rules snapshot (refresh it if AWS shipped new rules)",
            file=sys.stderr,
        )
        for cid, slug in list(skipped_unknown_slug.items())[:10]:
            print(f"    {cid} -> {slug}", file=sys.stderr)

    # Merge mode (default): preserve curated entries that aren't currently
    # exposed by AWS docs. Replace mode: wholesale-rewrite. Curated entries get
    # marked `_provenance_per_key` for traceability.
    final_mappings = dict(mappings)
    preserved_curated: dict[str, str] = {}
    overwritten: list[tuple[str, str, str]] = []
    if not args.replace and args.output.exists():
        try:
            existing = json.loads(args.output.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            existing = {}
        for k, v in existing.items():
            if k.startswith("_") or not isinstance(v, str):
                continue
            if k in final_mappings:
                if final_mappings[k] != v:
                    overwritten.append((k, v, final_mappings[k]))
                continue
            # Curated entry that the live docs don't currently expose. Preserve.
            final_mappings[k] = v
            preserved_curated[k] = v
        if preserved_curated:
            print(
                f"merge: preserved {len(preserved_curated)} curated entr{'y' if len(preserved_curated)==1 else 'ies'} "
                f"that the live docs no longer expose (use --replace to drop them).",
                file=sys.stderr,
            )
        if overwritten:
            print(
                f"merge: live docs changed mapping for {len(overwritten)} control(s) "
                f"(sample: {overwritten[:3]})",
                file=sys.stderr,
            )

    today = _dt.date.today().isoformat()
    out: dict[str, Any] = {
        "_comment": (
            "Curated Security Hub control_id -> AWS Config managed-rule kebab slug. "
            "Generated by scripts/refresh_sh_control_crosswalk.py from the AWS Security "
            "Hub per-service controls pages."
        ),
        "_source": INDEX_URL,
        "_format": "control_id (e.g., RDS.3) -> AWS Config managed-rule kebab slug (e.g., rds-storage-encrypted)",
        "_provenance": "aws-security-hub",
        "_refreshed": today,
        "_count": len(final_mappings),
        "_merged_curated_count": len(preserved_curated),
    }
    out.update(dict(sorted(final_mappings.items())))

    # Sanity guard: the *fresh* extraction (not the merged total) must clear
    # a floor. If extraction produced suspiciously few mappings the page
    # parser is chasing a stale format. Even with --merge preserving the
    # bundled set, that means refreshes won't pick up new AWS controls.
    MIN_EXPECTED_MAPPINGS = 50
    if not args.print_only and len(mappings) < MIN_EXPECTED_MAPPINGS:
        print(
            f"refused to write snapshot: only {len(mappings)} mappings extracted "
            f"(expected >= {MIN_EXPECTED_MAPPINGS}); per-service page format may have changed.",
            file=sys.stderr,
        )
        print(
            "Inspect a per-service page (e.g., acm-controls.html) and update "
            "PER_SERVICE_LINK_RE / CONFIG_RULE_LABEL_RE if so. "
            "Use --print-only to dump what was extracted without overwriting.",
            file=sys.stderr,
        )
        return 2

    text = json.dumps(out, indent=2) + "\n"
    if args.print_only:
        sys.stdout.write(text)
    else:
        args.output.write_text(text, encoding="utf-8")
        if preserved_curated:
            print(
                f"wrote {len(final_mappings)} entries to {args.output} "
                f"({len(mappings)} from live docs + {len(preserved_curated)} preserved curated)",
                file=sys.stderr,
            )
        else:
            print(f"wrote {len(final_mappings)} entries to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
