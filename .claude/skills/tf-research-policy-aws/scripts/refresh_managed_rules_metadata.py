#!/usr/bin/env python3
"""Refresh `references/managed-rules-metadata.json` by fetching each AWS
Config managed rule's developer-guide page and parsing the metadata fields
the bulk enricher consumes.

This is a maintenance script — runs are slow (one HTTP fetch per rule, ~250
rules in a full snapshot). Run when AWS publishes new managed rules or when
existing rule pages have changed materially.

Strategy:
  * The page at https://docs.aws.amazon.com/config/latest/developerguide/<slug>.html
    contains the rule's title, parameters, evaluation logic, severity (where
    AWS publishes one), and resource types.
  * We parse with a simple HTML→text transform plus heading-aware splitting.
    Fields not present on the page are left unset; bulk_enrich.py treats them
    as snapshot misses.

Usage:
  scripts/refresh_managed_rules_metadata.py
  scripts/refresh_managed_rules_metadata.py --rule-ids S3_BUCKET_VERSIONING_ENABLED,RDS_STORAGE_ENCRYPTED
  scripts/refresh_managed_rules_metadata.py --rule-list /tmp/priority.json --merge
"""
from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import re
import sys
import urllib.error
from html.parser import HTMLParser
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _common import REFERENCES, http_get, screaming_to_kebab  # noqa: E402

DEFAULT_OUTPUT = REFERENCES / "managed-rules-metadata.json"
DEFAULT_RULE_LIST = REFERENCES / "managed-rules.txt"


class _DocParser(HTMLParser):
    """HTML-to-text parser oriented at AWS Config developer-guide rule pages.

    The pages have a deterministic structure: an H1 with the rule title, followed
    by sections like "Trigger type", "Resource Types", "Parameters", and either an
    intro paragraph or a "How the rule evaluates" section. The original parser missed
    intro text that appears BEFORE any subheading, which is where AWS often puts the
    rule's primary description. This version captures both: an `intro_text` blob
    and a `sections` dict keyed by lowercase heading.
    """

    _SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside"}

    def __init__(self) -> None:
        super().__init__()
        self.current_heading: str | None = None
        self.sections: dict[str, list[str]] = {}
        self.intro_text: list[str] = []
        self.title: str = ""
        self._capture_h1 = False
        self._capture_heading = False
        self._heading_buf: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "h1":
            self._capture_h1 = True
        elif tag in ("h2", "h3", "h4"):
            self._capture_heading = True
            self._heading_buf = []

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if tag == "h1":
            self._capture_h1 = False
        elif tag in ("h2", "h3", "h4"):
            self._capture_heading = False
            self.current_heading = " ".join(self._heading_buf).strip()
            if self.current_heading:
                self.sections.setdefault(self.current_heading.lower(), [])
        elif tag in ("p", "li", "div"):
            # Soft separator so adjacent <p>foo</p><p>bar</p> reads as "foo bar".
            target = self.sections.get(self.current_heading.lower()) if self.current_heading else self.intro_text
            if target is not None:
                target.append(" ")

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        if self._capture_h1 and not self.title:
            self.title += data
            return
        if self._capture_heading:
            self._heading_buf.append(data)
            return
        if self.current_heading:
            self.sections.setdefault(self.current_heading.lower(), []).append(data)
        else:
            self.intro_text.append(data)


def _section_text(parser: _DocParser, *headings: str, fallback_to_intro: bool = False) -> str:
    """Find the first matching section text.

    If fallback_to_intro is True and no heading matches, returns the intro text
    (paragraphs above the first subheading). Many AWS Config rule pages put the
    canonical description in this position. Caller controls whether the fallback
    applies — remediation must NEVER fall back to intro because that would alias
    remediation to description, which is misleading.
    """
    for h in headings:
        for key, parts in parser.sections.items():
            if h.lower() in key:
                joined = "".join(parts)
                joined = re.sub(r"\s+", " ", joined).strip()
                if joined:
                    return joined
    if fallback_to_intro:
        intro = re.sub(r"\s+", " ", "".join(parser.intro_text)).strip()
        if intro and len(intro) > 30:
            return intro[:600]
    return ""


def _service_from_identifier(identifier: str) -> str:
    """Heuristic: leading prefix of the SCREAMING_SNAKE_CASE id is the service."""
    head = identifier.split("_", 1)[0].lower()
    aliases = {
        "s3": "s3", "rds": "rds", "iam": "iam", "ec2": "ec2", "kms": "kms",
        "cloudtrail": "cloudtrail", "cloudwatch": "cloudwatch", "vpc": "vpc",
        "ecr": "ecr", "ecs": "ecs", "elb": "elb", "elbv2": "elbv2",
        "lambda": "lambda", "guardduty": "guardduty", "wafv2": "wafv2",
        "redshift": "redshift", "dynamodb": "dynamodb", "efs": "efs",
        "elasticache": "elasticache", "elasticsearch": "opensearch",
        "secretsmanager": "secretsmanager", "ssm": "ssm", "sns": "sns",
        "sqs": "sqs", "sagemaker": "sagemaker", "stepfunctions": "stepfunctions",
        "appsync": "appsync", "apigateway": "apigateway", "athena": "athena",
        "autoscaling": "autoscaling", "backup": "backup",
        "codebuild": "codebuild", "codepipeline": "codepipeline",
        "config": "config", "datasync": "datasync", "dms": "dms",
        "ebs": "ec2", "fsx": "fsx", "lex": "lex", "macie": "macie",
        "mq": "mq", "msk": "kafka", "neptune": "neptune",
        "opensearch": "opensearch", "rbin": "ec2",
        "documentdb": "docdb", "kinesis": "kinesis",
    }
    return aliases.get(head, head)


def _extract_main_content(html: str) -> str:
    """Slice the HTML to the AWS docs main-col-body div, removing site nav.

    AWS Config developer-guide pages wrap the actual rule content in
    `<div id="main-col-body">...</div>`. Without this slice the parser ingests
    the page header, "View a markdown version of this page" banner, copyright
    footer, and other boilerplate that has nothing to do with the rule.
    """
    m = re.search(r'<div[^>]*id="main-col-body"[^>]*>', html, re.IGNORECASE)
    if not m:
        return html
    start = m.end()
    # Match up to the next sibling-level closing div or </main>.
    # Heuristic: look for the surrounding awsdocs-content close. Cap at the next 60k chars.
    snippet = html[start:start + 60000]
    return snippet


def parse_rule_page(html: str, identifier: str) -> dict[str, Any] | None:
    body = _extract_main_content(html)
    p = _DocParser()
    try:
        p.feed(body)
    except Exception:
        return None
    raw_title = re.sub(r"\s+", " ", p.title).strip()
    # The H1 on AWS Config rule pages is often the rule slug itself
    # ("s3-bucket-versioning-enabled"). Distill to a human-friendly title from
    # the identifier when the H1 is just the slug.
    if not raw_title or raw_title.lower() == screaming_to_kebab(identifier):
        title = identifier.replace("_", " ").title()
    else:
        title = raw_title
    requirement = _section_text(p, "Description", "Trigger type", fallback_to_intro=True)
    condition_desc = _section_text(p, "How the rule evaluates", "Trigger type", fallback_to_intro=True)
    if not condition_desc:
        condition_desc = requirement
    remediation = _section_text(p, "Remediation", "Remediation steps", "Resolution")  # NO intro fallback
    if not remediation and condition_desc:
        # Many pages don't have a dedicated remediation section. Synthesize a
        # generic line from the rule's identifier so the snapshot entry is never
        # empty. Tag _remediation_source so downstream knows it's a fallback.
        remediation = (
            f"Configure the resource to satisfy the rule {identifier}. "
            f"See the AWS Config developer guide for the rule for parameter details and "
            f"specific remediation steps."
        )
    parameters: dict[str, Any] = {}
    params_text = _section_text(p, "Parameters")
    if params_text:
        for m in re.finditer(r"\b([a-zA-Z][a-zA-Z0-9]+)\s*:\s*([A-Za-z]+)", params_text):
            parameters.setdefault(m.group(1), None)
    severity = _extract_severity(html)
    resource_types = _extract_resource_types(html)
    condition_logic = _derive_condition_logic(identifier, condition_desc, parameters)

    # Quality guard: if we still have empty string fields after parsing AND fallback,
    # the page format is unusual. Return None so the rule lands in `_missing` and
    # the caller can hand-curate. Don't write half-empty entries to the snapshot.
    if not requirement or not condition_desc:
        return None

    out = {
        "title": title,
        "service": _service_from_identifier(identifier),
        "severity": severity or "MEDIUM",
        "framework_control_requirement": requirement,
        "condition_description": condition_desc,
        "condition_logic": condition_logic,
        "remediation_summary": remediation,
        "documentation_url": f"https://docs.aws.amazon.com/config/latest/developerguide/{screaming_to_kebab(identifier)}.html",
        "resource_types": resource_types,
        "parameters": parameters,
        "_provenance": "aws-config-managed-rule-doc",
        "_severity_source": "page" if severity else "default",
        "_snapshot_date": datetime.date.today().isoformat(),
    }
    if "Configure the resource to satisfy the rule" in remediation:
        out["_remediation_source"] = "synthesized-fallback"
    return out


def _smart_merge_entry(
    old: dict[str, Any],
    new: dict[str, Any],
    rid: str,
    preserved_fields: dict[str, list[str]],
) -> dict[str, Any]:
    """Merge `new` into `old`, preserving curated fields when the refresh fell back.

    The dev-guide page is thin for many rules — no severity, kebab-cased h1 as
    the only "title", and no structured evaluation logic. The first refresh
    populated the bundled snapshot from a richer source (Security Hub controls
    / hand curation). A subsequent `--merge` refresh that mechanically scrapes
    the page would otherwise downgrade those curated values back to defaults.

    Rules:
      * If `new` flagged a field as default/fallback (`_severity_source ==
        'default'`, `_remediation_source == 'synthesized-fallback'`), keep the
        existing value for the corresponding payload field.
      * If the existing `title` is human-readable (contains a space and is not
        just the title-cased kebab slug), keep it. The page's `<h1>` is the
        kebab slug for most rules, which the parser title-cases to "Ec2 Imdsv2
        Check"-style.
      * If the existing `condition_logic` is a real expression (contains `==`,
        `<`, `>`, `AND`, `OR`, etc., AND is not the fallback `complies_with(...)`
        placeholder), keep it.
      * resource_types: prefer the union (new rule may add a type AWS just
        added; the curated snapshot may have a remapped type the parser
        doesn't apply).
      * Always overwrite `documentation_url`, `parameters`, `_snapshot_date`
        with the new values — those are facts the page is authoritative for.
      * For fields not handled above, take `new` (the parser knows best what
        the page says today).
    """
    merged = dict(new)
    preserved: list[str] = []

    # Severity: keep curated value if the refresh fell back to default.
    if new.get("_severity_source") == "default" and old.get("severity"):
        merged["severity"] = old["severity"]
        merged["_severity_source"] = old.get("_severity_source", "curated")
        preserved.append("severity")

    # Remediation: keep curated remediation if the refresh fell back.
    if new.get("_remediation_source") == "synthesized-fallback" and old.get("remediation_summary"):
        old_rem = old["remediation_summary"]
        if old_rem and "Configure the resource to satisfy the rule" not in old_rem:
            merged["remediation_summary"] = old_rem
            merged.pop("_remediation_source", None)
            preserved.append("remediation_summary")

    # Title: keep curated title if it's a real human-readable sentence and the
    # refresh produced just the kebab→TitleCase fallback.
    old_title = old.get("title", "") or ""
    new_title = new.get("title", "") or ""
    looks_like_kebab_titlecase = (
        new_title.replace(" ", "-").lower() == rid.lower().replace("_", "-")
    )
    old_title_real = (" " in old_title.strip()) and (
        old_title.replace(" ", "-").lower() != rid.lower().replace("_", "-")
    )
    if looks_like_kebab_titlecase and old_title_real:
        merged["title"] = old_title
        preserved.append("title")

    # condition_logic: keep curated logic if refresh fell back to placeholder.
    new_logic = new.get("condition_logic", "") or ""
    old_logic = old.get("condition_logic", "") or ""
    placeholder_logic = "complies_with(" in new_logic and "==" in new_logic and len(new_logic) < 80
    real_old_logic = old_logic and (
        any(op in old_logic for op in ("==", "!=", " AND ", " OR ", " in ", "contains"))
        and "complies_with(" not in old_logic
    )
    if placeholder_logic and real_old_logic:
        merged["condition_logic"] = old_logic
        preserved.append("condition_logic")

    # framework_control_requirement: keep the longer, richer description.
    old_req = old.get("framework_control_requirement", "") or ""
    new_req = new.get("framework_control_requirement", "") or ""
    if len(old_req) > len(new_req) * 1.2 and len(old_req) > 50:
        merged["framework_control_requirement"] = old_req
        preserved.append("framework_control_requirement")

    # condition_description: same reasoning — keep richer text.
    old_desc = old.get("condition_description", "") or ""
    new_desc = new.get("condition_description", "") or ""
    if len(old_desc) > len(new_desc) * 1.2 and len(old_desc) > 50:
        merged["condition_description"] = old_desc
        preserved.append("condition_description")

    # resource_types: union (page may add new types AWS shipped; bundled
    # snapshot may have remapped legacy names like AWS::OpenSearch::Domain).
    old_rt = old.get("resource_types") or []
    new_rt = new.get("resource_types") or []
    if isinstance(old_rt, list) and isinstance(new_rt, list):
        union = list({*old_rt, *new_rt})
        if union and union != new_rt:
            merged["resource_types"] = sorted(union)
            preserved.append("resource_types")

    if preserved:
        preserved_fields[rid] = preserved
    return merged


def _extract_severity(html: str) -> str | None:
    m = re.search(r"\bSeverity\b\s*[:\-]?\s*(Critical|High|Medium|Low|Informational)", html, re.I)
    if m:
        return m.group(1).upper()
    return None


def _extract_resource_types(html: str) -> list[str]:
    return sorted(set(re.findall(r"AWS::[A-Za-z0-9]+::[A-Za-z0-9]+", html)))


def _derive_condition_logic(identifier: str, description: str, parameters: dict[str, Any]) -> str:
    """Best-effort templated condition.logic from the rule identifier and description.

    Replaced by snapshot-extracted values when the rule already has a maintained entry.
    """
    desc_low = description.lower()
    if "non_compliant" in desc_low or "non-compliant" in desc_low:
        # Many AWS Config rules describe behaviour in this form. Distill to a
        # compliance check expression. Worst case: "evaluates as compliant when ..." stub.
        return f"resource.complies_with('{identifier}') == True"
    return f"resource.complies_with('{identifier}') == True"


def fetch_rule(identifier: str) -> dict[str, Any] | None:
    slug = screaming_to_kebab(identifier)
    url = f"https://docs.aws.amazon.com/config/latest/developerguide/{slug}.html"
    try:
        html = http_get(url)
    except urllib.error.HTTPError as e:
        print(f"  {identifier}: HTTP {e.code} {url}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"  {identifier}: fetch error: {e}", file=sys.stderr)
        return None
    parsed = parse_rule_page(html, identifier)
    return parsed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rule-ids", help="comma-separated SCREAMING_SNAKE_CASE identifiers")
    ap.add_argument("--rule-list", type=pathlib.Path,
                    help="newline-delimited identifiers (default: references/managed-rules.txt)")
    ap.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--merge", action="store_true",
                    help="merge into existing snapshot rather than rewriting")
    ap.add_argument("--limit", type=int, default=0, help="cap on rules to process (0=all)")
    args = ap.parse_args()

    ids: list[str] = []
    if args.rule_ids:
        ids.extend(s.strip().upper() for s in args.rule_ids.split(",") if s.strip())
    elif args.rule_list:
        text = args.rule_list.read_text(encoding="utf-8")
        if args.rule_list.suffix == ".json":
            ids.extend(json.loads(text))
        else:
            ids.extend(line.strip().upper() for line in text.splitlines()
                       if line.strip() and not line.startswith("#"))
    else:
        ids.extend(line.strip().upper() for line in DEFAULT_RULE_LIST.read_text("utf-8").splitlines()
                   if line.strip() and not line.startswith("#"))

    if args.limit:
        ids = ids[: args.limit]
    print(f"refreshing metadata for {len(ids)} rules ...")

    existing: dict[str, Any] = {}
    if args.merge and args.output.exists():
        existing = json.loads(args.output.read_text(encoding="utf-8"))

    updated = dict(existing)
    missing: list[str] = []
    preserved_fields: dict[str, list[str]] = {}
    for n, rid in enumerate(ids, 1):
        if n % 25 == 0:
            print(f"  ... {n}/{len(ids)}")
        entry = fetch_rule(rid)
        if entry is None:
            missing.append(rid)
            continue
        # Field-level smart merge: when refreshing an existing rule, do not let
        # a default/fallback-quality refresh value clobber a curated value that
        # was extracted from a richer source (Security Hub, hand-curated). The
        # parser tags low-confidence values via `_severity_source: 'default'`
        # and `_remediation_source: 'synthesized-fallback'`; the smart merge
        # treats those as "do not overwrite" signals.
        if args.merge and rid in existing:
            entry = _smart_merge_entry(existing[rid], entry, rid, preserved_fields)
        updated[rid] = entry

    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {k: updated[k] for k in sorted(updated)}
    if missing:
        payload["_missing"] = missing
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"wrote {args.output} ({len(payload) - (1 if '_missing' in payload else 0)} rules; {len(missing)} missing)")
    if preserved_fields:
        # Surface which rules had curated values protected from a downgrading refresh.
        # When the dev-guide page lacks structured fields the parser falls back to
        # defaults; the smart merge keeps the higher-quality existing values.
        print(f"preserved curated fields on {len(preserved_fields)} rule(s) (--merge protected against page-format weakness):")
        for rid, fields in sorted(preserved_fields.items())[:20]:
            print(f"  {rid}: {', '.join(fields)}")
        if len(preserved_fields) > 20:
            print(f"  ... and {len(preserved_fields) - 20} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
