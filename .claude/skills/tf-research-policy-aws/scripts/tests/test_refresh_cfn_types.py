"""Tests for scripts/refresh_cfn_types.py.

`refresh_cfn_types` is the simplest of the refresh scripts — it parses one JSON
document. The risk here isn't subtle merge logic, it's silent breakage if AWS
restructures the CFN Resource Specification or if the script's output format
drifts away from what `validate_yaml.py` expects to load.
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
import refresh_cfn_types as R  # noqa: E402


class TestExtractAndWrite(unittest.TestCase):
    def test_extract_from_minimal_spec(self) -> None:
        """The CFN spec uses `ResourceTypes` as the top-level key with the type
        names as keys. We only need the names — the rest of the spec is large
        and irrelevant to validate_yaml's offline check."""
        spec = {
            "ResourceTypes": {
                "AWS::EC2::Instance": {"Properties": {}},
                "AWS::S3::Bucket": {"Properties": {}},
                "AWS::IAM::Role": {"Properties": {}},
            },
            "PropertyTypes": {},
            "ResourceSpecificationVersion": "1.0.0",
        }
        types = R.extract_types(spec)
        self.assertEqual(types, ["AWS::EC2::Instance", "AWS::IAM::Role", "AWS::S3::Bucket"])

    def test_writes_snapshot_with_header(self) -> None:
        """The snapshot file has a comment header documenting source URL +
        refresh date. validate_yaml.py loads the file via load_text_snapshot
        which strips comment lines, so the header is human-only metadata."""
        with tempfile.NamedTemporaryFile("w+", suffix=".txt", delete=False) as f:
            path = pathlib.Path(f.name)
        try:
            R.write_snapshot(path, ["AWS::EC2::Instance", "AWS::S3::Bucket"])
            text = path.read_text()
            self.assertIn("# CloudFormation Resource Specification snapshot", text)
            self.assertIn("# Source:", text)
            self.assertIn("# Refreshed:", text)
            self.assertIn("AWS::EC2::Instance\nAWS::S3::Bucket\n", text)
        finally:
            path.unlink(missing_ok=True)

    def test_extract_handles_missing_resource_types_key(self) -> None:
        """If the spec doc is malformed (or AWS renames the top-level key),
        we should return an empty list rather than crash. Caller decides
        whether the empty list is fatal."""
        spec = {"PropertyTypes": {}, "ResourceSpecificationVersion": "1.0.0"}
        self.assertEqual(R.extract_types(spec), [])


if __name__ == "__main__":
    unittest.main()
