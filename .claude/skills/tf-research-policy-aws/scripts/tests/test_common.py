"""Tests for scripts/_common.py shared utilities."""
from __future__ import annotations

import json
import pathlib
import sys
import tempfile
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import _common  # noqa: E402


class TestIsTodo(unittest.TestCase):
    def test_todo_string(self):
        self.assertTrue(_common.is_todo("TODO: anything"))
        self.assertTrue(_common.is_todo("  TODO: with whitespace  "))

    def test_non_todo(self):
        self.assertFalse(_common.is_todo("MEDIUM"))
        self.assertFalse(_common.is_todo(""))
        self.assertFalse(_common.is_todo(None))
        self.assertFalse(_common.is_todo({"k": "TODO: v"}))


class TestKebab(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_common.kebab("Hello World"), "hello-world")

    def test_punctuation_collapse(self):
        self.assertEqual(_common.kebab("S3 / Bucket -- public!"), "s3-bucket-public")

    def test_empty(self):
        self.assertEqual(_common.kebab(""), "")
        self.assertEqual(_common.kebab(None), "")


class TestScreamingToKebab(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_common.screaming_to_kebab("RDS_STORAGE_ENCRYPTED"), "rds-storage-encrypted")

    def test_already_kebab(self):
        self.assertEqual(_common.screaming_to_kebab("rds-storage-encrypted"), "rds-storage-encrypted")


class TestLoadJsonRemap(unittest.TestCase):
    def test_strips_metadata_keys(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "remap.json"
            p.write_text(json.dumps({
                "_comment": "ignore me",
                "_provenance": "manual",
                "OLD_NAME": "NEW_NAME",
                "OTHER_OLD": "OTHER_NEW",
            }), encoding="utf-8")
            out = _common.load_json_remap(p)
            self.assertEqual(out, {"OLD_NAME": "NEW_NAME", "OTHER_OLD": "OTHER_NEW"})

    def test_missing_file_returns_empty(self):
        self.assertEqual(_common.load_json_remap(pathlib.Path("/no/such/file.json")), {})


class TestSnapshotAge(unittest.TestCase):
    def test_parses_refreshed_header(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "snap.txt"
            p.write_text(
                "# Some snapshot\n# Refreshed: 2020-01-01\n# Source: somewhere\n\nentry-one\n",
                encoding="utf-8",
            )
            age = _common.snapshot_age_days(p)
            self.assertIsNotNone(age)
            assert age is not None  # for mypy
            self.assertGreater(age, 1000)  # 6+ years

    def test_missing_header_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "snap.txt"
            p.write_text("# Just a comment\nentry-one\n", encoding="utf-8")
            self.assertIsNone(_common.snapshot_age_days(p))

    def test_load_text_snapshot(self):
        with tempfile.TemporaryDirectory() as td:
            p = pathlib.Path(td) / "snap.txt"
            p.write_text("# header\nfoo\n\nbar\n# comment\nbaz\n", encoding="utf-8")
            self.assertEqual(_common.load_text_snapshot(p), {"foo", "bar", "baz"})


if __name__ == "__main__":
    unittest.main()
