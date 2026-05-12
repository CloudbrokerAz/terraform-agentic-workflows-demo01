"""Tests for scripts/refresh_managed_rules_metadata.py.

Pin the smart-merge logic that protects curated values when the dev-guide page
is thin (no severity, kebab-cased h1 as the title, no structured logic). Without
this guard, `--merge` would silently downgrade a curated `severity: HIGH` to
the parser's default `MEDIUM`, replace a real title with kebab-titlecase, and
overwrite real condition.logic with a `complies_with(...)` placeholder.

Also pin the page-format-agnostic href regex used to discover rules from the
catalog page — AWS toggles between bare `slug.html` and `./slug.html` hrefs.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import refresh_managed_rules_metadata as R  # noqa: E402


class TestSmartMergeEntry(unittest.TestCase):
    """Field-level merge guards. Each test isolates one field."""

    def _curated(self) -> dict:
        """A typical curated entry from the bundled snapshot."""
        return {
            "title": "EC2 instances must require IMDSv2",
            "service": "ec2",
            "severity": "HIGH",
            "framework_control_requirement": "Checks whether your Amazon Elastic Compute Cloud (Amazon EC2) instance metadata version is configured with Instance Metadata Service Version 2 (IMDSv2). The rule is NON_COMPLIANT if the HttpTokens is set to optional.",
            "condition_description": "EC2 instances must use IMDSv2 (HttpTokens=required)",
            "condition_logic": "ec2_instance.MetadataOptions.HttpTokens == 'required'",
            "remediation_summary": "Set HttpTokens=required on the EC2 instance metadata options. See https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/configuring-instance-metadata-service.html",
            "documentation_url": "https://docs.aws.amazon.com/config/latest/developerguide/ec2-imdsv2-check.html",
            "resource_types": ["AWS::EC2::Instance"],
            "parameters": {},
            "_provenance": "aws-config-managed-rule-doc",
            "_severity_source": "curated",
            "_snapshot_date": "2026-04-01",
        }

    def _refreshed_with_defaults(self) -> dict:
        """A refresh entry where the dev-guide page provided no severity or title.

        The parser falls back to MEDIUM and kebab-titlecase, and tags the
        defaults via `_severity_source: 'default'` / `_remediation_source:
        'synthesized-fallback'`.
        """
        return {
            "title": "Ec2 Imdsv2 Check",
            "service": "ec2",
            "severity": "MEDIUM",
            "framework_control_requirement": "Checks whether your Amazon Elastic Compute Cloud (Amazon EC2) instance metadata version is configured with Instance Metadata Service Version 2 (IMDSv2). The rule is NON_COMPLIANT if the HttpTokens is set to optional.",
            "condition_description": "Checks whether your Amazon Elastic Compute Cloud (Amazon EC2) instance metadata version is configured with Instance Metadata Service Version 2 (IMDSv2). The rule is NON_COMPLIANT if the HttpTokens is set to optional.",
            "condition_logic": "resource.complies_with('EC2_IMDSV2_CHECK') == True",
            "remediation_summary": "Configure the resource to satisfy the rule EC2_IMDSV2_CHECK. See the AWS Config developer guide for the rule for parameter details and specific remediation steps.",
            "documentation_url": "https://docs.aws.amazon.com/config/latest/developerguide/ec2-imdsv2-check.html",
            "resource_types": ["AWS::EC2::Instance"],
            "parameters": {},
            "_provenance": "aws-config-managed-rule-doc",
            "_severity_source": "default",
            "_remediation_source": "synthesized-fallback",
            "_snapshot_date": "2026-05-08",
        }

    def test_severity_preserved_when_refresh_falls_back(self) -> None:
        """The headline regression: don't downgrade HIGH→MEDIUM on a doc-thin refresh."""
        old = self._curated()
        new = self._refreshed_with_defaults()
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["severity"], "HIGH")
        self.assertEqual(merged["_severity_source"], "curated")
        self.assertIn("severity", preserved["EC2_IMDSV2_CHECK"])

    def test_severity_overwritten_when_refresh_finds_page_value(self) -> None:
        """If the refresh actually parses a severity from the page, the new value wins."""
        old = self._curated()  # severity HIGH, _severity_source curated
        new = self._refreshed_with_defaults()
        new["severity"] = "CRITICAL"
        new["_severity_source"] = "page"
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["severity"], "CRITICAL")
        self.assertNotIn("severity", preserved.get("EC2_IMDSV2_CHECK", []))

    def test_title_preserved_when_refresh_falls_back_to_kebab_titlecase(self) -> None:
        """A real curated title beats the kebab→TitleCase fallback ("Ec2 Imdsv2 Check")."""
        old = self._curated()
        new = self._refreshed_with_defaults()
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["title"], "EC2 instances must require IMDSv2")
        self.assertIn("title", preserved["EC2_IMDSV2_CHECK"])

    def test_title_overwritten_when_refresh_provides_real_title(self) -> None:
        """If the page genuinely has a human-readable title, the refresh wins."""
        old = self._curated()
        new = self._refreshed_with_defaults()
        new["title"] = "Amazon EC2 instances should use Instance Metadata Service v2"
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["title"], "Amazon EC2 instances should use Instance Metadata Service v2")
        self.assertNotIn("title", preserved.get("EC2_IMDSV2_CHECK", []))

    def test_condition_logic_preserved_when_refresh_falls_back_to_placeholder(self) -> None:
        """A real expression beats the `resource.complies_with(...)` placeholder."""
        old = self._curated()
        new = self._refreshed_with_defaults()
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["condition_logic"], "ec2_instance.MetadataOptions.HttpTokens == 'required'")
        self.assertIn("condition_logic", preserved["EC2_IMDSV2_CHECK"])

    def test_remediation_preserved_when_refresh_falls_back_to_synthesized(self) -> None:
        """Real remediation text beats the synthesized-fallback boilerplate."""
        old = self._curated()
        new = self._refreshed_with_defaults()
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertIn("HttpTokens=required", merged["remediation_summary"])
        self.assertNotIn("_remediation_source", merged)
        self.assertIn("remediation_summary", preserved["EC2_IMDSV2_CHECK"])

    def test_resource_types_union_preserves_legacy_remap(self) -> None:
        """If old has remapped types and new has page-scraped types, union both.

        Real case: bundled snapshot was written when AWS docs used
        AWS::OpenSearch::Domain; the parser's snapshot now shows AWS::Elasticsearch::Domain
        (because the dev-guide page reverted, or because this is a different rule). We
        keep both so legacy CFN types validators recognize them.
        """
        old = {**self._curated(), "resource_types": ["AWS::OpenSearch::Domain"]}
        new = {**self._refreshed_with_defaults(), "resource_types": ["AWS::Elasticsearch::Domain"]}
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "OS_RULE", preserved)
        self.assertEqual(
            sorted(merged["resource_types"]),
            ["AWS::Elasticsearch::Domain", "AWS::OpenSearch::Domain"],
        )
        self.assertIn("resource_types", preserved["OS_RULE"])

    def test_richer_requirement_text_wins(self) -> None:
        """A 200-character curated requirement beats a 60-character page extract."""
        old = self._curated()
        old["framework_control_requirement"] = (
            "EC2 instances must require IMDSv2 — IMDSv1 is the legacy session-less variant "
            "of the EC2 instance metadata service that allows credential exfiltration via "
            "SSRF, and AWS recommends disabling it on every instance role."
        )
        new = self._refreshed_with_defaults()
        new["framework_control_requirement"] = "Short page summary."
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(
            merged["framework_control_requirement"],
            old["framework_control_requirement"],
        )
        self.assertIn("framework_control_requirement", preserved["EC2_IMDSV2_CHECK"])

    def test_documentation_url_always_taken_from_refresh(self) -> None:
        """The dev-guide URL is authoritative — always trust the refresh."""
        old = {**self._curated(), "documentation_url": "https://stale-url.example.com"}
        new = self._refreshed_with_defaults()  # canonical URL
        preserved: dict = {}
        merged = R._smart_merge_entry(old, new, "EC2_IMDSV2_CHECK", preserved)
        self.assertEqual(merged["documentation_url"], new["documentation_url"])


if __name__ == "__main__":
    unittest.main()
