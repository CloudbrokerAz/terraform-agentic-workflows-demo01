"""Tests for scripts/refresh_managed_rules.py.

Pin the href extraction regex against the two formats AWS toggles between on the
managed-rules catalog page (`<slug>.html` and `./<slug>.html`). The bug we
caught in production: AWS switched to `./` prefix and the previous regex parsed
zero identifiers, leading the script to abort under its sanity-check guard. A
silent regex drift would produce empty snapshots; we want to lock both forms in.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import refresh_managed_rules as R  # noqa: E402


def _catalog_page(href_form: str) -> str:
    """Build a tiny catalog HTML page using the chosen href form.

    Real catalog page has hundreds of rule links. Three is enough to pin the
    regex without dragging the test into snapshot-of-AWS territory.
    """
    rules = ["s3-bucket-versioning-enabled", "ec2-imdsv2-check", "rds-storage-encrypted"]
    if href_form == "bare":
        anchors = "\n".join(f'<a href="{r}.html">{r}</a>' for r in rules)
    elif href_form == "dotslash":
        anchors = "\n".join(f'<a href="./{r}.html">{r}</a>' for r in rules)
    elif href_form == "mixed":
        anchors = "\n".join(
            f'<a href="{prefix}{r}.html">{r}</a>'
            for prefix, r in zip(["", "./", ""], rules)
        )
    else:
        raise ValueError(href_form)
    return f"<html><body>{anchors}<a href='managed-rules-by-aws-config.html'>self</a></body></html>"


class TestExtractIdentifiers(unittest.TestCase):
    def test_bare_href_form(self) -> None:
        """The original AWS docs format: `href="slug.html"`."""
        ids = R.extract_identifiers(_catalog_page("bare"))
        self.assertEqual(ids, ["ec2-imdsv2-check", "rds-storage-encrypted", "s3-bucket-versioning-enabled"])

    def test_dotslash_href_form(self) -> None:
        """The format AWS migrated to: `href="./slug.html"`. Without the regex
        update this returns []."""
        ids = R.extract_identifiers(_catalog_page("dotslash"))
        self.assertEqual(ids, ["ec2-imdsv2-check", "rds-storage-encrypted", "s3-bucket-versioning-enabled"])

    def test_mixed_form_handled(self) -> None:
        """Belt-and-braces — if the page mixes formats during a transition, all rules parse."""
        ids = R.extract_identifiers(_catalog_page("mixed"))
        self.assertEqual(len(ids), 3)

    def test_self_link_skipped(self) -> None:
        """The catalog page links to itself; that should be filtered."""
        ids = R.extract_identifiers(_catalog_page("bare"))
        self.assertNotIn("managed-rules-by-aws-config", ids)

    def test_single_word_skipped(self) -> None:
        """The skip list filters single-word index pages, but rule slugs always
        contain a hyphen — verify that single-word hrefs are excluded."""
        html = '<a href="overview.html">x</a><a href="evaluate-config.html">y</a>'
        ids = R.extract_identifiers(html)
        self.assertEqual(ids, [])

    def test_writes_snapshot_with_header(self) -> None:
        """The snapshot file's header must record the source URL and refresh date."""
        import tempfile
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
            path = pathlib.Path(f.name)
        try:
            R.write_snapshot(path, ["a-rule", "b-rule"])
            text = path.read_text()
            self.assertIn("# AWS Config managed rules catalog snapshot", text)
            self.assertIn("# Source:", text)
            self.assertIn("# Refreshed:", text)
            self.assertIn("a-rule\nb-rule\n", text)
        finally:
            path.unlink(missing_ok=True)


class TestRefuseEmptyExtraction(unittest.TestCase):
    """The defensive guard that protects against silent doc-format drift."""

    def test_main_exits_2_when_zero_identifiers(self) -> None:
        """Subprocess-style invocation: when the URL returns nothing parseable,
        the script must refuse to write rather than emit an empty snapshot."""
        import tempfile
        from unittest.mock import patch

        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
            output_path = pathlib.Path(f.name)
        # Pre-populate with a known marker so we can assert it stays untouched.
        output_path.write_text("PRE_REFRESH_MARKER\n")
        try:
            with patch("refresh_managed_rules.fetch_catalog", return_value="<html><body>no links</body></html>"):
                with patch.object(sys, "argv", ["refresh_managed_rules.py", "--output", str(output_path)]):
                    rc = R.main()
            self.assertEqual(rc, 2)
            self.assertEqual(output_path.read_text(), "PRE_REFRESH_MARKER\n")
        finally:
            output_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
