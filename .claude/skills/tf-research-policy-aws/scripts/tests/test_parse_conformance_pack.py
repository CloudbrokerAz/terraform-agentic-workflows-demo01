"""Tests for scripts/parse_conformance_pack.py.

Pin: legacy identifier remap, legacy CFN type remap, process-check handling,
URL provenance attribution (constructed URLs tag aws-config-managed-rule-doc,
not aws-conformance-pack).
"""
from __future__ import annotations

import pathlib
import sys
import unittest

import yaml

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import parse_conformance_pack as P  # noqa: E402

FIXTURES = THIS.parent / "fixtures"


def _build_doc():
    text = (FIXTURES / "conformance-pack-mini.yaml").read_text(encoding="utf-8")
    template = P.parse_template(text)
    return P.build_document(template, "Test", "1.0", "file:///fixture")


class TestLegacyRemap(unittest.TestCase):
    def test_legacy_identifier_remapped(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        legacy = ids["cloud-trail-enabled"]
        # Legacy CLOUD_TRAIL_ENABLED maps to CLOUDTRAIL_ENABLED
        self.assertEqual(legacy["source"]["identifier"], "CLOUDTRAIL_ENABLED")
        # documentation_url uses the canonical kebab slug
        self.assertIn("cloudtrail-enabled", legacy["source"]["documentation_url"])

    def test_legacy_cfn_type_remapped(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        acm = ids["acm-certificate-expiration-check"]
        self.assertIn("AWS::CertificateManager::Certificate", acm["resource_types"])
        self.assertNotIn("AWS::ACM::Certificate", acm["resource_types"])

    def test_process_check_demoted_to_custom(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        pc = ids["example-process-check"]
        # Process-check rules become custom rules so the validator's
        # managed-rules check doesn't reject AWS_CONFIG_PROCESS_CHECK.
        self.assertEqual(pc["source"]["type"], "aws-config-custom-rule")


class TestProvenanceAttribution(unittest.TestCase):
    def test_documentation_url_tagged_managed_rule_doc(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        sse = ids["s3-bucket-server-side-encryption-enabled"]
        prov = sse["provenance"]
        # URL is constructed by the parser, not in the pack.
        self.assertEqual(prov["source.documentation_url"], "aws-config-managed-rule-doc")

    def test_source_identifier_tagged_conformance_pack(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        sse = ids["s3-bucket-server-side-encryption-enabled"]
        prov = sse["provenance"]
        # Identifier IS in the pack.
        self.assertEqual(prov["source.identifier"], "aws-conformance-pack")

    def test_references_includes_managed_rule_doc(self):
        doc = _build_doc()
        ids = {r["id"]: r for r in doc["rules"]}
        sse = ids["s3-bucket-server-side-encryption-enabled"]
        prov = sse["provenance"]
        refs_prov = prov["references"]
        # references[0] is constructed against the developer guide; tag accordingly.
        if isinstance(refs_prov, list):
            self.assertIn("aws-config-managed-rule-doc", refs_prov)
        else:
            self.assertEqual(refs_prov, "aws-config-managed-rule-doc")


class TestRoundTripYaml(unittest.TestCase):
    def test_output_yaml_is_valid(self):
        doc = _build_doc()
        text = yaml.safe_dump(doc, sort_keys=False)
        re_parsed = yaml.safe_load(text)
        self.assertEqual(len(re_parsed["rules"]), 4)


if __name__ == "__main__":
    unittest.main()
