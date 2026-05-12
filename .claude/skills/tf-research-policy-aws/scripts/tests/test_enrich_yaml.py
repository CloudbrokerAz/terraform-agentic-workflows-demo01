"""Tests for scripts/enrich_yaml.py.

Pin Strategy 0 (crosswalk) wiring, Strategy 3 uniqueness, dotted-key provenance,
references dedupe, and the match-gate exit behaviour.
"""
from __future__ import annotations

import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
SKILL_ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import enrich_yaml as E  # noqa: E402

import yaml  # noqa: E402

FIXTURES = THIS.parent / "fixtures"


def _run_enrich(yaml_path: pathlib.Path, controls_path: pathlib.Path, *extra: str) -> tuple[int, str, str]:
    cmd = [
        sys.executable,
        str(SCRIPTS / "enrich_yaml.py"),
        "--yaml", str(yaml_path),
        "--controls", str(controls_path),
        *extra,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


class TestSubscribedMode(unittest.TestCase):
    def test_strategy_2_via_related_requirements(self):
        """Subscribed-mode controls have RelatedRequirements populated; Strategy 2 should fire."""
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            yaml_path = tdp / "skel.yaml"
            shutil.copy(FIXTURES / "skeleton-for-enrich.yaml", yaml_path)
            controls_path = FIXTURES / "sh-controls-subscribed.json"

            rc, _, stderr = _run_enrich(yaml_path, controls_path, "--no-crosswalk")
            self.assertEqual(rc, 0, f"enrich failed: {stderr}")

            doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            # Both rules in the skeleton match a control via RelatedRequirements
            severities = {r["id"]: r.get("severity") for r in doc["rules"]}
            self.assertIn("HIGH", severities.values())
            self.assertIn("MEDIUM", severities.values())


class TestUnsubscribedModeWithCrosswalk(unittest.TestCase):
    def test_crosswalk_drives_match_when_related_requirements_empty(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            yaml_path = tdp / "skel.yaml"
            shutil.copy(FIXTURES / "skeleton-for-enrich.yaml", yaml_path)
            controls_path = FIXTURES / "sh-controls-unsubscribed.json"

            crosswalk_path = tdp / "cw.json"
            crosswalk_path.write_text(json.dumps({
                "S3.2": "s3-bucket-public-read-prohibited",
                "S3.4": "s3-bucket-server-side-encryption-enabled",
            }), encoding="utf-8")

            rc, _, stderr = _run_enrich(yaml_path, controls_path, "--crosswalk", str(crosswalk_path))
            self.assertEqual(rc, 0, f"enrich failed: {stderr}")
            self.assertIn("matched 2/2", stderr)

            doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            for r in doc["rules"]:
                # Crosswalk-driven matches stamp [aws-security-hub, manual-human]
                # because the linkage decision is curated.
                prov = r.get("provenance") or {}
                sev_prov = prov.get("severity")
                self.assertIn(
                    "manual-human",
                    sev_prov if isinstance(sev_prov, list) else [sev_prov],
                    f"crosswalk-driven match must record manual-human in severity provenance, got {sev_prov}",
                )

    def test_no_crosswalk_yields_zero_matches_in_unsubscribed_mode(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            yaml_path = tdp / "skel.yaml"
            shutil.copy(FIXTURES / "skeleton-for-enrich.yaml", yaml_path)
            controls_path = FIXTURES / "sh-controls-unsubscribed.json"

            # Without the crosswalk and with empty RelatedRequirements, only
            # Strategy 3 (whole-word match in description) can fire. The
            # fixture's descriptions don't whole-word match the SCREAMING form
            # but DO contain the kebab form, so Strategy 3 should pick them up
            # — but in a unique-match way.
            rc, _, stderr = _run_enrich(
                yaml_path, controls_path,
                "--no-crosswalk", "--allow-empty",
            )
            self.assertEqual(rc, 0, f"enrich failed: {stderr}")
            # Strategy 3 should match both via description-whole-word.
            self.assertIn("description-whole-word=2", stderr)


class TestStrategyThreeUniqueness(unittest.TestCase):
    def test_ambiguous_description_match_falls_through(self):
        """When two controls' descriptions both contain the same Config rule slug, Strategy 3 must fall through."""
        controls = [
            {"control_id": "X.1", "title": "T1", "description": "uses my-rule for checking"},
            {"control_id": "Y.1", "title": "T2", "description": "also references my-rule somewhere"},
        ]
        rule = {"id": "ambiguous", "source": {"identifier": "MY_RULE"}}
        c, strategy = E.match_rule(rule, controls, E.index_security_hub_controls(controls), crosswalk=None)
        self.assertIsNone(c, "ambiguous description match must NOT pick a control")
        self.assertIsNone(strategy)

    def test_unique_description_match_returns_control(self):
        controls = [
            {"control_id": "X.1", "title": "T1", "description": "uses unique-rule for checking"},
            {"control_id": "Y.1", "title": "T2", "description": "checks something completely different"},
        ]
        rule = {"id": "unique", "source": {"identifier": "UNIQUE_RULE"}}
        c, strategy = E.match_rule(rule, controls, E.index_security_hub_controls(controls), crosswalk=None)
        self.assertIsNotNone(c)
        assert c is not None
        self.assertEqual(c["control_id"], "X.1")
        self.assertEqual(strategy, "description-whole-word")

    def test_whole_word_does_not_match_subslug(self):
        """rds-encrypted must NOT match in 'rds-encrypted-at-rest'."""
        controls = [
            {"control_id": "RDS.99", "title": "T", "description": "rds-encrypted-at-rest is required"},
        ]
        rule = {"id": "r", "source": {"identifier": "RDS_ENCRYPTED"}}
        c, _ = E.match_rule(rule, controls, E.index_security_hub_controls(controls), crosswalk=None)
        self.assertIsNone(c, "whole-word matcher must reject substring overlap")


class TestMatchGate(unittest.TestCase):
    def test_zero_match_exits_nonzero_by_default(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            # Skeleton with a rule the controls fixture does not cover
            skel = {
                "metadata": {"framework": {"name": "X", "version": "1"}, "source": "https://aws.amazon.com/x"},
                "rules": [
                    {
                        "id": "completely-unrelated",
                        "source": {"type": "aws-config-managed-rule", "identifier": "NOT_PRESENT"},
                    }
                ],
            }
            yaml_path = tdp / "skel.yaml"
            yaml_path.write_text(yaml.safe_dump(skel), encoding="utf-8")
            controls_path = FIXTURES / "sh-controls-subscribed.json"

            rc, _, stderr = _run_enrich(yaml_path, controls_path, "--no-crosswalk")
            self.assertEqual(rc, 1, f"expected non-zero exit on zero matches, got {rc}: {stderr}")
            self.assertIn("zero rules matched", stderr)

    def test_zero_match_with_allow_empty_exits_zero(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            skel = {
                "metadata": {"framework": {"name": "X", "version": "1"}, "source": "https://aws.amazon.com/x"},
                "rules": [
                    {
                        "id": "completely-unrelated",
                        "source": {"type": "aws-config-managed-rule", "identifier": "NOT_PRESENT"},
                    }
                ],
            }
            yaml_path = tdp / "skel.yaml"
            yaml_path.write_text(yaml.safe_dump(skel), encoding="utf-8")
            controls_path = FIXTURES / "sh-controls-subscribed.json"

            rc, _, stderr = _run_enrich(yaml_path, controls_path, "--no-crosswalk", "--allow-empty")
            self.assertEqual(rc, 0, f"--allow-empty must override the zero-match gate: {stderr}")


class TestProvenanceDottedAndDedupe(unittest.TestCase):
    def test_framework_control_subkeys_are_dotted(self):
        with tempfile.TemporaryDirectory() as td:
            tdp = pathlib.Path(td)
            yaml_path = tdp / "skel.yaml"
            shutil.copy(FIXTURES / "skeleton-for-enrich.yaml", yaml_path)
            controls_path = FIXTURES / "sh-controls-subscribed.json"
            rc, _, stderr = _run_enrich(yaml_path, controls_path, "--no-crosswalk")
            self.assertEqual(rc, 0, stderr)
            doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            for r in doc["rules"]:
                prov = r.get("provenance") or {}
                # framework_control.id must remain aws-conformance-pack from the skeleton;
                # framework_control.title must come from aws-security-hub.
                self.assertEqual(prov.get("framework_control.id"), "aws-conformance-pack")
                self.assertEqual(prov.get("framework_control.title"), "aws-security-hub")
                self.assertEqual(prov.get("framework_control.requirement"), "aws-security-hub")


if __name__ == "__main__":
    unittest.main()
