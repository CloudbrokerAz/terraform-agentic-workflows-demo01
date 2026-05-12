"""Tests for scripts/validate_yaml.py.

Pin the contract: required fields, enum membership, snapshot lookups,
condition.logic heuristic, dotted-key provenance walk, manual-human vs
manual-model-synthesised under strict mode, AWS-domain URL allowlist.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

import yaml

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
SKILL_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import validate_yaml as V  # noqa: E402

FIXTURES = THIS.parent / "fixtures"


def _example_doc() -> dict:
    return yaml.safe_load((SKILL_ROOT / "references" / "example-rules.yaml").read_text(encoding="utf-8"))


def _bad_doc() -> dict:
    return yaml.safe_load((FIXTURES / "known-bad.yaml").read_text(encoding="utf-8"))


def _bundled():
    managed = V.load_text_snapshot(SKILL_ROOT / "references" / "managed-rules.txt")
    cfn = V.load_text_snapshot(SKILL_ROOT / "references" / "cfn-resource-types.txt")
    pseudo = V.load_text_snapshot(SKILL_ROOT / "references" / "aws-config-pseudo-types.txt")
    catalog = V.load_provenance_catalog(SKILL_ROOT / "references" / "aws-official-provenance.json")
    allow = V.load_domain_allowlist(SKILL_ROOT / "references" / "aws-domain-allowlist.txt")
    return managed, cfn, pseudo, catalog, allow


class TestExampleRulesPasses(unittest.TestCase):
    def test_default_mode(self):
        doc = _example_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(doc, managed, cfn, pseudo, provenance_catalog=catalog, domain_allowlist=allow)
        self.assertEqual(errors, [])

    def test_strict_aws_official(self):
        doc = _example_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(
            doc, managed, cfn, pseudo,
            provenance_catalog=catalog, domain_allowlist=allow,
            strict_aws_official=True,
        )
        self.assertEqual(errors, [], f"unexpected strict errors: {errors}")


class TestKnownBadFails(unittest.TestCase):
    def test_default_mode_collects_errors(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(doc, managed, cfn, pseudo, provenance_catalog=catalog, domain_allowlist=allow)
        joined = "\n".join(errors)
        self.assertIn("severity 'SUPER_CRITICAL'", joined)
        self.assertIn("source.type 'bogus-source-type'", joined)
        # Bad rule 1 references a malformed CFN type:
        self.assertIn("notavalidcfntype", joined)
        # Bad rule 2 references a managed-rule slug not in the snapshot:
        self.assertIn("not in managed rules snapshot", joined)
        # Bad rule 1 has TODO in condition.logic:
        self.assertIn("condition.logic still has TODO", joined)

    def test_condition_logic_trivia_warns(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        _, warnings = V.validate_document(doc, managed, cfn, pseudo, provenance_catalog=catalog, domain_allowlist=allow)
        joined = "\n".join(warnings)
        self.assertIn("condition.logic 'true' is too trivial", joined)

    def test_strict_aws_official_rejects_third_party(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(
            doc, managed, cfn, pseudo,
            provenance_catalog=catalog, domain_allowlist=allow,
            strict_aws_official=True,
        )
        joined = "\n".join(errors)
        self.assertIn("third-party-prowler", joined)

    def test_strict_rejects_model_synthesis_by_default(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(
            doc, managed, cfn, pseudo,
            provenance_catalog=catalog, domain_allowlist=allow,
            strict_aws_official=True,
        )
        joined = "\n".join(errors)
        self.assertIn("manual-model-synthesised", joined)

    def test_allow_model_synthesis_lets_it_through(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(
            doc, managed, cfn, pseudo,
            provenance_catalog=catalog, domain_allowlist=allow,
            strict_aws_official=True,
            allow_model_synthesis=True,
        )
        joined = "\n".join(errors)
        # Still rejected: third-party-prowler. Not rejected: manual-model-synthesised.
        self.assertIn("third-party-prowler", joined)
        self.assertNotIn(
            "manual-model-synthesised", joined,
            "manual-model-synthesised must be allowed when --allow-model-synthesis is set",
        )

    def test_strict_rejects_non_aws_metadata_source(self):
        doc = _bad_doc()
        managed, cfn, pseudo, catalog, allow = _bundled()
        errors, _ = V.validate_document(
            doc, managed, cfn, pseudo,
            provenance_catalog=catalog, domain_allowlist=allow,
            strict_aws_official=True,
        )
        joined = "\n".join(errors)
        self.assertIn("metadata.source URL 'https://example.com/not-aws'", joined)


class TestDottedProvenanceWalk(unittest.TestCase):
    def test_dotted_keys_are_inspected(self):
        prov = {
            "framework_control.id": "aws-conformance-pack",
            "framework_control.title": "third-party-prowler",
            "severity": ["aws-security-hub", "third-party-trivy"],
            "_metadata": "ignored",
        }
        leaves = dict(V.walk_provenance(prov))
        self.assertIn("framework_control.id", leaves)
        self.assertIn("framework_control.title", leaves)
        self.assertEqual(leaves["framework_control.title"], "third-party-prowler")
        self.assertNotIn("_metadata", leaves)

    def test_collect_non_aws_finds_third_party_in_dotted_key(self):
        catalog = V.load_provenance_catalog(SKILL_ROOT / "references" / "aws-official-provenance.json")
        rule = {
            "provenance": {
                "framework_control.id": "aws-conformance-pack",
                "framework_control.title": "third-party-prowler",
                "severity": ["aws-security-hub", "third-party-trivy"],
            }
        }
        bad = V.collect_non_aws_provenance(rule, catalog, allow_model_synthesis=False)
        keys = {field for field, _ in bad}
        self.assertEqual(keys, {"framework_control.title", "severity"})


class TestUrlAllowlist(unittest.TestCase):
    def test_subdomain_match(self):
        allow = V.load_domain_allowlist(SKILL_ROOT / "references" / "aws-domain-allowlist.txt")
        self.assertTrue(V.url_on_aws_domain("https://docs.aws.amazon.com/foo", allow))
        self.assertTrue(V.url_on_aws_domain("https://aws.amazon.com/bar", allow))

    def test_github_org_path_prefix(self):
        allow = V.load_domain_allowlist(SKILL_ROOT / "references" / "aws-domain-allowlist.txt")
        self.assertTrue(V.url_on_aws_domain("https://github.com/awslabs/aws-config-rules", allow))
        self.assertFalse(V.url_on_aws_domain("https://github.com/some-other-org/repo", allow))

    def test_unrelated_domain_rejected(self):
        allow = V.load_domain_allowlist(SKILL_ROOT / "references" / "aws-domain-allowlist.txt")
        self.assertFalse(V.url_on_aws_domain("https://example.com/foo", allow))

    def test_empty_allowlist_disables_check(self):
        self.assertTrue(V.url_on_aws_domain("https://anywhere.example", []))


class TestConditionLogicHeuristic(unittest.TestCase):
    def _r(self, logic):
        return {"condition": {"logic": logic}}

    def test_trivial_value_warns(self):
        warnings = V.check_condition_logic(self._r("true"), "rid")
        self.assertTrue(any("too trivial" in w for w in warnings))

    def test_no_operator_warns(self):
        warnings = V.check_condition_logic(self._r("encryption is enabled"), "rid")
        # Lowercase "is" isn't in operator set; expect a warning.
        self.assertTrue(any("comparison/membership operator" in w for w in warnings))

    def test_real_logic_passes(self):
        warnings = V.check_condition_logic(self._r("resource.StorageEncrypted == true"), "rid")
        self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
