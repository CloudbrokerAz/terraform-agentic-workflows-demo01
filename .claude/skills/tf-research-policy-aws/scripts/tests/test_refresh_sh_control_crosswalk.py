"""Tests for scripts/refresh_sh_control_crosswalk.py.

Pin three classes of behaviour that the production bug-hunt exposed:

1.  **Per-service link discovery** must work against both bare `<slug>-controls.html`
    hrefs (older format) and `./<slug>-controls.html` (current). AWS toggled to
    the relative-prefixed form on the per-standard pages; without regex updates
    we discovered zero pages.

2.  **AWS Config rule extraction** must handle both wrappers:
        Format A: <p><b>AWS Config rule:</b> <a href="...">slug</a></p>
        Format B: <p><b>AWS Config rule:</b> <code class="code">slug</code></p>
    AWS uses Format A for managed rules and Format B for Security Hub CSPM
    custom rules. The label-tag also drifts between <b>...</b> and <strong>...</strong>.

3.  **Sanity guard + merge** must not silently wipe curated entries on
    extraction failure or trim. The whole crosswalk's value to downstream
    `enrich_yaml.py` depends on it being non-empty in unsubscribed mode.
"""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import refresh_sh_control_crosswalk as R  # noqa: E402


# ---------------------------------------------------------------------------
# Per-service link discovery: PER_SERVICE_LINK_RE
# ---------------------------------------------------------------------------

class TestFetchPerServiceLinks(unittest.TestCase):
    def test_bare_hrefs(self) -> None:
        """Original docs format — `href="acm-controls.html"`."""
        html = (
            '<a href="acm-controls.html">x</a>'
            '<a href="apigateway-controls.html">x</a>'
            '<a href="cloudtrail-controls.html">x</a>'
        )
        self.assertEqual(
            R.fetch_per_service_links(html),
            ["acm-controls.html", "apigateway-controls.html", "cloudtrail-controls.html"],
        )

    def test_dotslash_hrefs(self) -> None:
        """Current docs format on per-standard pages — `href="./acm-controls.html"`.

        Without the `(?:\\./)?` prefix in the regex this returns []."""
        html = (
            '<a href="./acm-controls.html#acm-1">[ACM.1]</a>'
            '<a href="./apigateway-controls.html#apigateway-1">[APIGateway.1]</a>'
        )
        self.assertEqual(
            R.fetch_per_service_links(html),
            ["acm-controls.html", "apigateway-controls.html"],
        )

    def test_anchor_fragment_stripped(self) -> None:
        """Per-standard pages link with `#anchor` suffixes; the regex should
        capture only the page name."""
        html = '<a href="./acm-controls.html#acm-1">[ACM.1]</a>'
        links = R.fetch_per_service_links(html)
        self.assertEqual(links, ["acm-controls.html"])
        self.assertNotIn("acm-controls.html#acm-1", links)

    def test_dedupes_repeated_links(self) -> None:
        """A standard page may link to the same per-service file once per control;
        we want the page once."""
        html = (
            '<a href="./acm-controls.html#acm-1">[ACM.1]</a>'
            '<a href="./acm-controls.html#acm-2">[ACM.2]</a>'
            '<a href="./acm-controls.html#acm-3">[ACM.3]</a>'
        )
        self.assertEqual(R.fetch_per_service_links(html), ["acm-controls.html"])


# ---------------------------------------------------------------------------
# Control + Config-rule extraction: extract_mappings
# ---------------------------------------------------------------------------

class TestExtractMappings(unittest.TestCase):
    def _section(self, control_id: str, label_tag: str, slug_block: str) -> str:
        """Build a minimal per-service-page section for one control."""
        return (
            f'<h2 id="{control_id.lower().replace(".","-")}">[{control_id}] Title text</h2>'
            f"<p><b>Severity:</b> Medium</p>"
            f"<p>{label_tag}AWS Config rule:</{label_tag.replace('<','/').rstrip('>') if label_tag.startswith('<') else 'b'}> {slug_block}</p>"
        )

    def test_format_a_anchor(self) -> None:
        """Managed-rule format: slug inside `<a href="...">slug</a>`. The most
        common shape on current per-service pages."""
        html = (
            '<h2 id="acm-1">[ACM.1] Imported certificates should be renewed</h2>'
            '<p><b>AWS Config rule:</b> '
            '<a href="https://docs.aws.amazon.com/config/latest/developerguide/'
            'acm-certificate-expiration-check.html">acm-certificate-expiration-check</a></p>'
        )
        self.assertEqual(
            R.extract_mappings(html),
            {"ACM.1": "acm-certificate-expiration-check"},
        )

    def test_format_b_code(self) -> None:
        """Security Hub CSPM custom-rule format: slug inside <code>slug</code>.
        Caught the production bug where only Format B was matched.
        Without the dual-form regex, ACM.3 returned empty."""
        html = (
            '<h2 id="acm-3">[ACM.3] ACM certificates should be tagged</h2>'
            '<p><b>AWS Config rule:</b> '
            '<code class="code">tagged-acm-certificate</code> '
            "(custom Security Hub CSPM rule)</p>"
        )
        self.assertEqual(
            R.extract_mappings(html),
            {"ACM.3": "tagged-acm-certificate"},
        )

    def test_strong_label_wrapper(self) -> None:
        """Some standard pages use <strong>...</strong> instead of <b>...</b>
        for the label."""
        html = (
            '<h2 id="rds-3">[RDS.3] Storage encryption</h2>'
            '<p><strong>AWS Config rule:</strong> '
            '<a href="rds-storage-encrypted.html">rds-storage-encrypted</a></p>'
        )
        self.assertEqual(
            R.extract_mappings(html),
            {"RDS.3": "rds-storage-encrypted"},
        )

    def test_managed_rule_label_variant(self) -> None:
        """Some pages say "AWS Config managed rule" instead of "AWS Config rule"."""
        html = (
            '<h2 id="s3-1">[S3.1] Block public access</h2>'
            '<p><b>AWS Config managed rule:</b> '
            '<a href="s3-bucket-public-read-prohibited.html">s3-bucket-public-read-prohibited</a></p>'
        )
        self.assertEqual(
            R.extract_mappings(html),
            {"S3.1": "s3-bucket-public-read-prohibited"},
        )

    def test_multiple_controls_same_page(self) -> None:
        """A per-service page lists every control for that service. The walker
        must split on each `[XXX.N]` heading and find the rule within that
        section, not match across sections."""
        html = (
            '<h2 id="acm-1">[ACM.1] Renewal</h2>'
            '<p><b>AWS Config rule:</b> '
            '<a href="acm-certificate-expiration-check.html">acm-certificate-expiration-check</a></p>'
            '<h2 id="acm-2">[ACM.2] RSA key length</h2>'
            '<p><b>AWS Config rule:</b> '
            '<a href="acm-certificate-rsa-check.html">acm-certificate-rsa-check</a></p>'
            '<h2 id="acm-3">[ACM.3] Tagging</h2>'
            '<p><b>AWS Config rule:</b> '
            '<code class="code">tagged-acm-certificate</code> (custom)</p>'
        )
        self.assertEqual(
            R.extract_mappings(html),
            {
                "ACM.1": "acm-certificate-expiration-check",
                "ACM.2": "acm-certificate-rsa-check",
                "ACM.3": "tagged-acm-certificate",
            },
        )

    def test_skips_none_slug(self) -> None:
        """The catch-all literal `<code>none</code>` is not a rule slug; skip it."""
        html = (
            '<h2 id="ssm-1">[SSM.1] No rule</h2>'
            '<p><b>AWS Config rule:</b> <code class="code">none</code></p>'
        )
        self.assertEqual(R.extract_mappings(html), {})

    def test_no_config_rule_section_returns_empty(self) -> None:
        """A control without an `AWS Config rule:` row should produce no mapping
        rather than a false positive against unrelated <code> tags on the page."""
        html = (
            '<h2 id="iam-1">[IAM.1] Some control</h2>'
            '<p><b>Severity:</b> High</p>'
            '<p>Other text with <code>random</code> code blocks</p>'
        )
        self.assertEqual(R.extract_mappings(html), {})


# ---------------------------------------------------------------------------
# Sanity guard + merge: end-to-end via main()
# ---------------------------------------------------------------------------

class TestMainSanityAndMerge(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = pathlib.Path(self._tmp.name)
        # A managed-rules.txt fixture so the cross-check has slugs to match against.
        self.rules_snapshot = self.tmpdir / "managed-rules.txt"
        self.rules_snapshot.write_text(
            "# header\n"
            "acm-certificate-expiration-check\n"
            "acm-certificate-rsa-check\n"
            "rds-storage-encrypted\n"
            "s3-bucket-public-read-prohibited\n"
            "s3-bucket-server-side-encryption-enabled\n"
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _run_with_mocked_http(self, http_responses: dict[str, str], extra_argv: list[str] | None = None) -> tuple[int, pathlib.Path]:
        """Invoke main() with `http_get` patched to return canned HTML per URL."""
        from unittest.mock import patch

        output_path = self.tmpdir / "crosswalk.json"
        argv = [
            "refresh_sh_control_crosswalk.py",
            "--output", str(output_path),
            "--rules-snapshot", str(self.rules_snapshot),
        ]
        if extra_argv:
            argv.extend(extra_argv)

        def fake_http_get(url: str) -> str:
            if url in http_responses:
                return http_responses[url]
            for k, v in http_responses.items():
                if url.endswith(k.lstrip("./")):
                    return v
            return ""  # no content -> no links discovered

        with patch.object(sys, "argv", argv):
            with patch("refresh_sh_control_crosswalk.http_get", side_effect=fake_http_get):
                rc = R.main()
        return rc, output_path

    def test_sanity_guard_refuses_below_threshold(self) -> None:
        """When live extraction yields too few mappings, the script must exit 2
        and leave the existing crosswalk file untouched (preventing data loss
        when AWS docs format drifts)."""
        # Pre-populate a curated crosswalk.
        output_path = self.tmpdir / "crosswalk.json"
        existing = {
            "_provenance": "aws-security-hub",
            "RDS.3": "rds-storage-encrypted",
            "S3.1": "s3-bucket-public-read-prohibited",
        }
        output_path.write_text(json.dumps(existing) + "\n")

        # Mock HTTP responses: standard pages return a single per-service link;
        # per-service page returns one mapping (well below the 50-floor).
        responses = {url: "" for url in R.STANDARD_INDEX_URLS}
        responses[R.STANDARD_INDEX_URLS[0]] = '<a href="./acm-controls.html">x</a>'
        responses["acm-controls.html"] = (
            '<h2 id="acm-1">[ACM.1] Renewal</h2>'
            '<p><b>AWS Config rule:</b> '
            '<a href="acm-certificate-expiration-check.html">acm-certificate-expiration-check</a></p>'
        )
        rc, _ = self._run_with_mocked_http(responses)
        self.assertEqual(rc, 2)
        # File must be untouched
        on_disk = json.loads(output_path.read_text())
        self.assertEqual(on_disk["RDS.3"], "rds-storage-encrypted")
        self.assertEqual(on_disk["S3.1"], "s3-bucket-public-read-prohibited")

    def test_merge_preserves_curated_entries_not_in_live_docs(self) -> None:
        """When the live extraction yields enough mappings to clear the floor
        but the bundled crosswalk had OTHER curated entries the docs no longer
        expose, those curated entries must survive the refresh."""
        output_path = self.tmpdir / "crosswalk.json"
        # Curated set includes a control the live docs won't return.
        existing = {
            "_provenance": "aws-security-hub",
            "Legacy.99": "rds-storage-encrypted",
        }
        output_path.write_text(json.dumps(existing) + "\n")

        # Build mocked responses with > 50 mappings to clear the sanity floor.
        # Use a single per-service page that lists 60 numbered controls, each
        # mapping to one of the 5 known slugs.
        per_service = ""
        slugs = [
            "acm-certificate-expiration-check",
            "acm-certificate-rsa-check",
            "rds-storage-encrypted",
            "s3-bucket-public-read-prohibited",
            "s3-bucket-server-side-encryption-enabled",
        ]
        for i in range(60):
            slug = slugs[i % len(slugs)]
            per_service += (
                f'<h2 id="svc-{i}">[Svc.{i}] Control {i}</h2>'
                f'<p><b>AWS Config rule:</b> <a href="{slug}.html">{slug}</a></p>'
            )

        responses = {url: "" for url in R.STANDARD_INDEX_URLS}
        responses[R.STANDARD_INDEX_URLS[0]] = '<a href="./svc-controls.html">x</a>'
        responses["svc-controls.html"] = per_service
        rc, output_path = self._run_with_mocked_http(responses)
        self.assertEqual(rc, 0)

        on_disk = json.loads(output_path.read_text())
        # Live mappings are present.
        self.assertEqual(on_disk["Svc.0"], "acm-certificate-expiration-check")
        # Curated entry survives (key insight of the merge mode).
        self.assertEqual(on_disk["Legacy.99"], "rds-storage-encrypted")
        # And the metadata reports it.
        self.assertGreaterEqual(on_disk["_merged_curated_count"], 1)

    def test_replace_mode_drops_curated_entries(self) -> None:
        """`--replace` is the explicit opt-out — when the user has manually
        verified that the live docs are the new source of truth, drop the
        curated extras."""
        output_path = self.tmpdir / "crosswalk.json"
        existing = {
            "_provenance": "aws-security-hub",
            "Legacy.99": "rds-storage-encrypted",
        }
        output_path.write_text(json.dumps(existing) + "\n")

        per_service = ""
        slugs = [
            "acm-certificate-expiration-check",
            "rds-storage-encrypted",
            "s3-bucket-public-read-prohibited",
            "acm-certificate-rsa-check",
            "s3-bucket-server-side-encryption-enabled",
        ]
        for i in range(60):
            slug = slugs[i % len(slugs)]
            per_service += (
                f'<h2 id="svc-{i}">[Svc.{i}] Control {i}</h2>'
                f'<p><b>AWS Config rule:</b> <a href="{slug}.html">{slug}</a></p>'
            )
        responses = {url: "" for url in R.STANDARD_INDEX_URLS}
        responses[R.STANDARD_INDEX_URLS[0]] = '<a href="./svc-controls.html">x</a>'
        responses["svc-controls.html"] = per_service
        rc, output_path = self._run_with_mocked_http(responses, extra_argv=["--replace"])
        self.assertEqual(rc, 0)

        on_disk = json.loads(output_path.read_text())
        self.assertNotIn("Legacy.99", on_disk)
        self.assertEqual(on_disk["_merged_curated_count"], 0)


if __name__ == "__main__":
    unittest.main()
