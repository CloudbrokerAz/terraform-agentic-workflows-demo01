"""Tests for scripts/merge_yaml.py.

The P0 fix: provenance must survive merge. Without this, --strict-aws-official
either falsely passes (no third-party tags survive) or falsely fails (no
AWS-official tags survive). Either way the audit trail is destroyed.
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

import yaml

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import merge_yaml as M  # noqa: E402


def _rule(rid: str, **overrides) -> dict:
    base = {
        "id": rid,
        "title": f"Title for {rid}",
        "framework_control": {"id": rid + "-fc", "requirement": f"req {rid}"},
        "severity": "MEDIUM",
        "service": "s3",
        "resource_types": ["AWS::S3::Bucket"],
        "source": {
            "type": "aws-config-managed-rule",
            "identifier": rid.upper().replace("-", "_"),
            "documentation_url": f"https://docs.aws.amazon.com/{rid}.html",
        },
        "condition": {"description": "ok", "logic": "resource.x == true"},
        "remediation": {"summary": "ok"},
        "references": [{"title": "ref", "url": f"https://docs.aws.amazon.com/{rid}.html"}],
        "test_cases": [{"name": "t", "expected": "COMPLIANT"}],
    }
    base.update(overrides)
    return base


class TestProvenanceSurvives(unittest.TestCase):
    def test_primary_provenance_preserved(self):
        primary = _rule("a", provenance={"severity": "aws-security-hub"})
        secondary = _rule("a", severity="HIGH")
        out = M.merge_rules(primary, secondary)
        self.assertEqual(out.get("provenance", {}).get("severity"), "aws-security-hub")

    def test_secondary_provenance_added(self):
        primary = _rule("a", provenance={"severity": "aws-security-hub"})
        secondary = _rule(
            "a",
            severity="HIGH",
            provenance={"remediation.terraform_snippet": "third-party-prowler"},
        )
        out = M.merge_rules(primary, secondary)
        prov = out.get("provenance") or {}
        self.assertEqual(prov.get("severity"), "aws-security-hub")
        self.assertEqual(prov.get("remediation.terraform_snippet"), "third-party-prowler")

    def test_dedupe_when_same_value(self):
        primary = _rule("a", provenance={"references": "aws-conformance-pack"})
        secondary = _rule("a", provenance={"references": "aws-conformance-pack"})
        out = M.merge_rules(primary, secondary)
        # Same value collapses to scalar, not [x, x].
        self.assertEqual(out["provenance"]["references"], "aws-conformance-pack")

    def test_merge_to_list_when_different_values(self):
        primary = _rule("a", provenance={"references": "aws-conformance-pack"})
        secondary = _rule("a", provenance={"references": "aws-security-hub"})
        out = M.merge_rules(primary, secondary)
        refs = out["provenance"]["references"]
        self.assertIsInstance(refs, list)
        self.assertEqual(set(refs), {"aws-conformance-pack", "aws-security-hub"})

    def test_dotted_keys_preserved(self):
        primary = _rule("a", provenance={
            "framework_control.id": "aws-conformance-pack",
            "framework_control.title": "aws-security-hub",
        })
        secondary = _rule("a", provenance={
            "framework_control.requirement": "aws-security-hub",
        })
        out = M.merge_rules(primary, secondary)
        prov = out["provenance"]
        self.assertEqual(prov["framework_control.id"], "aws-conformance-pack")
        self.assertEqual(prov["framework_control.title"], "aws-security-hub")
        self.assertEqual(prov["framework_control.requirement"], "aws-security-hub")

    def test_metadata_keys_dropped(self):
        primary = _rule("a", provenance={
            "_comment": "should not survive",
            "severity": "aws-security-hub",
        })
        secondary = _rule("a")
        out = M.merge_rules(primary, secondary)
        self.assertNotIn("_comment", out["provenance"])

    def test_list_already_present_merges_with_dedup(self):
        primary = _rule("a", provenance={"references": ["aws-conformance-pack", "aws-security-hub"]})
        secondary = _rule("a", provenance={"references": ["aws-security-hub", "third-party-prowler"]})
        out = M.merge_rules(primary, secondary)
        refs = out["provenance"]["references"]
        self.assertEqual(refs, ["aws-conformance-pack", "aws-security-hub", "third-party-prowler"])


class TestEndToEndMergeFile(unittest.TestCase):
    def test_run_against_files_propagates_provenance(self):
        primary = {
            "metadata": {"framework": {"name": "Test", "version": "1"}, "source": "https://aws.amazon.com/x"},
            "rules": [_rule("a", provenance={"severity": "aws-security-hub"})],
        }
        secondary = {
            "metadata": {"framework": {"name": "Test", "version": "1"}, "source": "https://aws.amazon.com/x"},
            "rules": [_rule("a", severity="HIGH", provenance={"remediation.terraform_snippet": "third-party-prowler"})],
        }
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            p = tdp / "primary.yaml"
            s = tdp / "secondary.yaml"
            o = tdp / "merged.yaml"
            p.write_text(yaml.safe_dump(primary), encoding="utf-8")
            s.write_text(yaml.safe_dump(secondary), encoding="utf-8")
            import subprocess
            proc = subprocess.run(
                [sys.executable, str(SCRIPTS / "merge_yaml.py"),
                 "--primary", str(p), "--secondary", str(s), "--output", str(o)],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            merged = yaml.safe_load(o.read_text(encoding="utf-8"))
            rule = merged["rules"][0]
            self.assertIn("provenance", rule)
            self.assertEqual(rule["provenance"]["severity"], "aws-security-hub")
            self.assertEqual(rule["provenance"]["remediation.terraform_snippet"], "third-party-prowler")


if __name__ == "__main__":
    unittest.main()
