"""Tests for scripts/bulk_enrich.py.

bulk_enrich is the production-time path that converts a parse_conformance_pack
skeleton into a READY YAML — every framework run goes through it. The places
most likely to silently break and the places most expensive to break are:

1. **enrich_process_check** — the BNM RMiT regression: when a conformance pack
   defines a process-check rule with no Description (just ConfigRuleName +
   Source.Owner=AWS_CONFIG_PROCESS_CHECK), parse_conformance_pack leaves the
   rule's condition.description as a TODO. The current logic derives a title
   from the kebab rule id so the YAML still reaches READY without manual cleanup.

2. **_remap_cfn_types** — the validator-vs-snapshot reconciler. The bundled
   metadata snapshot mirrors AWS dev-guide pages verbatim, which still use
   legacy CFN type names (AWS::OpenSearch::Domain, AWS::ACM::Certificate). The
   bundled CFN snapshot uses the canonical post-rename names. Without remap on
   ingestion, validate_yaml flags the legacy names. This regressed once during
   the iter-13 BNM run; pinning prevents it.

3. **enrich_resource_types** — branching on snapshot-empty vs rule-empty vs
   force. Account-scoped fallback to AWS::::Account is the kind of edge case
   that breaks under refactor without anyone noticing.

4. **count_residual_todos** — the contract behind --require-zero-todos. If
   _REQUIRED_PATHS falls out of sync with the validator's required fields, the
   workflow's "fail fast" guarantee evaporates.

5. **The dotted-key helpers + provenance accumulator** — small but called from
   every enrich path; corruption here cascades.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import bulk_enrich as B  # noqa: E402


# ---------------------------------------------------------------------------
# Dotted-key helpers
# ---------------------------------------------------------------------------

class TestDottedKeyHelpers(unittest.TestCase):
    def test_get_dotted_nested(self) -> None:
        rule = {"condition": {"logic": "x == y"}}
        self.assertEqual(B.get_dotted(rule, "condition.logic"), "x == y")

    def test_get_dotted_missing_returns_none(self) -> None:
        rule = {"condition": {}}
        self.assertIsNone(B.get_dotted(rule, "condition.logic"))
        self.assertIsNone(B.get_dotted(rule, "missing.path"))

    def test_get_dotted_through_non_dict_returns_none(self) -> None:
        """If we hit a list/string mid-path, return None rather than crash."""
        rule = {"condition": "not a dict"}
        self.assertIsNone(B.get_dotted(rule, "condition.logic"))

    def test_set_dotted_creates_intermediate(self) -> None:
        rule: dict = {}
        changed = B.set_dotted(rule, "framework_control", "title", "Hello")
        self.assertTrue(changed)
        self.assertEqual(rule, {"framework_control": {"title": "Hello"}})

    def test_set_dotted_with_inner_key(self) -> None:
        rule: dict = {"framework_control": {"id": "X"}}
        changed = B.set_dotted(rule, "framework_control", "title", "T")
        self.assertTrue(changed)
        self.assertEqual(rule["framework_control"], {"id": "X", "title": "T"})

    def test_set_dotted_no_change_when_value_equal(self) -> None:
        rule: dict = {"severity": "HIGH"}
        self.assertFalse(B.set_dotted(rule, "severity", None, "HIGH"))


# ---------------------------------------------------------------------------
# Provenance accumulator
# ---------------------------------------------------------------------------

class TestTagProvenance(unittest.TestCase):
    def test_first_write_creates_string_value(self) -> None:
        rule: dict = {}
        B.tag_provenance(rule, "severity", "aws-config-managed-rule-doc")
        self.assertEqual(rule["provenance"], {"severity": "aws-config-managed-rule-doc"})

    def test_second_write_with_different_source_promotes_to_list(self) -> None:
        """When two phases populate the same field with different sources, we
        keep the audit trail by storing both. Strict-AWS-official validation
        relies on this — the auditor needs to see every source that touched
        the field, not just the latest."""
        rule = {"provenance": {"severity": "aws-config-managed-rule-doc"}}
        B.tag_provenance(rule, "severity", "aws-security-hub")
        self.assertEqual(
            rule["provenance"]["severity"],
            ["aws-config-managed-rule-doc", "aws-security-hub"],
        )

    def test_repeated_write_with_same_source_idempotent(self) -> None:
        """Re-running bulk_enrich on a YAML must not duplicate provenance entries."""
        rule = {"provenance": {"severity": "aws-config-managed-rule-doc"}}
        B.tag_provenance(rule, "severity", "aws-config-managed-rule-doc")
        self.assertEqual(rule["provenance"]["severity"], "aws-config-managed-rule-doc")

    def test_unknown_provenance_is_overwritten(self) -> None:
        """`unknown` is a placeholder the parser writes when no source is
        attributable. A real source coming in later replaces it rather than
        getting accumulated alongside the placeholder."""
        rule = {"provenance": {"severity": "unknown"}}
        B.tag_provenance(rule, "severity", "aws-config-managed-rule-doc")
        self.assertEqual(rule["provenance"]["severity"], "aws-config-managed-rule-doc")

    def test_list_provenance_appends_uniquely(self) -> None:
        rule = {"provenance": {"severity": ["aws-conformance-pack", "aws-security-hub"]}}
        B.tag_provenance(rule, "severity", "aws-config-managed-rule-doc")
        self.assertEqual(
            rule["provenance"]["severity"],
            ["aws-conformance-pack", "aws-security-hub", "aws-config-managed-rule-doc"],
        )

    def test_list_provenance_doesnt_double(self) -> None:
        rule = {"provenance": {"severity": ["aws-conformance-pack"]}}
        B.tag_provenance(rule, "severity", "aws-conformance-pack")
        self.assertEqual(rule["provenance"]["severity"], ["aws-conformance-pack"])


# ---------------------------------------------------------------------------
# needs_fill predicate
# ---------------------------------------------------------------------------

class TestNeedsFill(unittest.TestCase):
    def test_none_needs_fill(self) -> None:
        self.assertTrue(B.needs_fill(None, force=False))

    def test_empty_string_needs_fill(self) -> None:
        self.assertTrue(B.needs_fill("", force=False))
        self.assertTrue(B.needs_fill("   ", force=False))

    def test_todo_string_needs_fill(self) -> None:
        self.assertTrue(B.needs_fill("TODO: anything", force=False))

    def test_empty_list_needs_fill(self) -> None:
        self.assertTrue(B.needs_fill([], force=False))

    def test_empty_dict_needs_fill(self) -> None:
        self.assertTrue(B.needs_fill({}, force=False))

    def test_populated_string_no_fill(self) -> None:
        self.assertFalse(B.needs_fill("real value", force=False))

    def test_populated_list_no_fill(self) -> None:
        self.assertFalse(B.needs_fill(["item"], force=False))

    def test_force_overrides_populated(self) -> None:
        """--force exists for "AWS revised this rule's metadata; refresh it
        even if it looks fine". If --force doesn't override, --force is broken."""
        self.assertTrue(B.needs_fill("real value", force=True))


# ---------------------------------------------------------------------------
# Legacy CFN type remap — pins the iter-13 OpenSearch regression
# ---------------------------------------------------------------------------

class TestRemapCfnTypes(unittest.TestCase):
    def test_legacy_opensearch_remapped(self) -> None:
        """The bundled snapshot still says AWS::OpenSearch::Domain (matching
        AWS dev-guide pages); the canonical CFN spec uses
        AWS::OpenSearchService::Domain. Without remap, validate_yaml errors."""
        result = B._remap_cfn_types(["AWS::OpenSearch::Domain"])
        self.assertEqual(result, ["AWS::OpenSearchService::Domain"])

    def test_legacy_acm_remapped(self) -> None:
        """Same class of bug for ACM — dev-guide says AWS::ACM::Certificate,
        canonical CFN uses AWS::CertificateManager::Certificate."""
        result = B._remap_cfn_types(["AWS::ACM::Certificate"])
        self.assertEqual(result, ["AWS::CertificateManager::Certificate"])

    def test_canonical_types_pass_through(self) -> None:
        """Non-legacy types don't get rewritten."""
        types = ["AWS::EC2::Instance", "AWS::S3::Bucket", "AWS::IAM::Role"]
        self.assertEqual(B._remap_cfn_types(types), types)

    def test_mixed_list_remapped(self) -> None:
        """Real packs mix legacy and canonical types — handle each independently."""
        result = B._remap_cfn_types(["AWS::EC2::Instance", "AWS::OpenSearch::Domain", "AWS::S3::Bucket"])
        self.assertEqual(
            result,
            ["AWS::EC2::Instance", "AWS::OpenSearchService::Domain", "AWS::S3::Bucket"],
        )

    def test_empty_list_handled(self) -> None:
        self.assertEqual(B._remap_cfn_types([]), [])


# ---------------------------------------------------------------------------
# enrich_resource_types — branching logic with several edge cases
# ---------------------------------------------------------------------------

class TestEnrichResourceTypes(unittest.TestCase):
    def test_snapshot_replaces_todo(self) -> None:
        rule = {"resource_types": ["TODO: AWS::Service::Resource"]}
        changed = B.enrich_resource_types(rule, ["AWS::EC2::Instance"], force=False)
        self.assertTrue(changed)
        self.assertEqual(rule["resource_types"], ["AWS::EC2::Instance"])

    def test_snapshot_skips_when_already_populated(self) -> None:
        """Without --force, a real value the parse layer set should survive
        bulk_enrich. The snapshot is "fill in the blanks", not "rewrite
        everything"."""
        rule = {"resource_types": ["AWS::EC2::Instance"]}
        changed = B.enrich_resource_types(rule, ["AWS::S3::Bucket"], force=False)
        self.assertFalse(changed)
        self.assertEqual(rule["resource_types"], ["AWS::EC2::Instance"])

    def test_force_overwrites_populated(self) -> None:
        rule = {"resource_types": ["AWS::EC2::Instance"]}
        changed = B.enrich_resource_types(rule, ["AWS::S3::Bucket"], force=True)
        self.assertTrue(changed)
        self.assertEqual(rule["resource_types"], ["AWS::S3::Bucket"])

    def test_account_scoped_fallback_when_snapshot_empty_and_rule_todo(self) -> None:
        """Account-level Config rules (CLOUDTRAIL_SECURITY_TRAIL_ENABLED,
        SECURITYHUB_ENABLED, etc.) have no resource_types in the snapshot.
        We still need a non-TODO value for validate_yaml to pass — fall
        back to the AWS::::Account pseudo-type."""
        rule = {"resource_types": ["TODO: AWS::Service::Resource"]}
        changed = B.enrich_resource_types(rule, [], force=False)
        self.assertTrue(changed)
        self.assertEqual(rule["resource_types"], ["AWS::::Account"])

    def test_no_change_when_snapshot_empty_and_rule_populated(self) -> None:
        """If both snapshot and rule are populated/empty respectively, do nothing."""
        rule = {"resource_types": ["AWS::EC2::Instance"]}
        self.assertFalse(B.enrich_resource_types(rule, [], force=False))

    def test_resource_types_missing_treated_as_empty(self) -> None:
        """If resource_types isn't in the rule at all (parse layer omitted it),
        the snapshot value should fill — same as empty list."""
        rule: dict = {}
        changed = B.enrich_resource_types(rule, ["AWS::EC2::Instance"], force=True)
        self.assertTrue(changed)
        self.assertEqual(rule["resource_types"], ["AWS::EC2::Instance"])


# ---------------------------------------------------------------------------
# enrich_process_check — pins the BNM RMiT regression
# ---------------------------------------------------------------------------

class TestEnrichProcessCheck(unittest.TestCase):
    def _process_check_rule(self, description: str = "", rule_id: str = "response-plan-tested") -> dict:
        """Build a rule shaped like parse_conformance_pack's process-check output."""
        return {
            "id": rule_id,
            "title": "TODO: plain-English description of compliant state",
            "framework_control": {
                "id": "TODO: framework control ID (e.g., CIS 2.3.1)",
                "title": "TODO: plain-English description of compliant state",
                "requirement": "TODO: plain-English description of compliant state",
            },
            "severity": "TODO: severity",
            "service": "TODO: aws service slug",
            "resource_types": ["TODO: AWS::Service::Resource"],
            "source": {
                "type": "aws-config-custom-rule",
                "identifier": "AWS_CONFIG_PROCESS_CHECK",
                "documentation_url": "TODO: documentation URL",
            },
            "condition": {
                "description": description,
                "logic": "TODO: condition logic",
            },
            "remediation": {"summary": "TODO: remediation"},
            "references": [],
            "test_cases": [],
        }

    def test_happy_path_with_real_description(self) -> None:
        """A pack-supplied description (BNM RMiT does this for most rules)
        flows into title / framework_control.requirement and the rule is
        marked aws-conformance-pack provenance."""
        rule = self._process_check_rule(
            description="Confirm that the financial institution has a current, documented technology incident response plan that defines roles, responsibilities, and escalation paths."
        )
        stats = B.enrich_process_check(rule, force=False)
        self.assertGreater(stats["filled"], 0)
        self.assertNotIn("TODO", rule["title"])
        self.assertNotIn("TODO", rule["framework_control"]["requirement"])
        self.assertEqual(rule["severity"], "INFORMATIONAL")
        self.assertEqual(rule["condition"]["logic"], "manual_attestation_required == true")
        # Provenance: aws-conformance-pack for description-derived fields.
        self.assertEqual(rule["provenance"]["title"], "aws-conformance-pack")

    def test_bnm_regression_todo_description_derives_title_from_id(self) -> None:
        """The exact failure mode that surfaced during iter-13 BNM RMiT.

        The pack defines `ResponsePlanTested` with no Description field. The
        parser leaves condition.description as a TODO. The previous code
        would short-circuit on description being non-empty (TODO IS
        non-empty), then propagate the TODO string into title and
        framework_control.requirement. Result: validator-failing YAML.

        After the fix: derive a title from the kebab rule id, populate every
        required field, mark provenance manual-human."""
        rule = self._process_check_rule(
            description="TODO: plain-English description of compliant state",
            rule_id="response-plan-tested",
        )
        stats = B.enrich_process_check(rule, force=False)
        self.assertGreater(stats["filled"], 0)
        self.assertEqual(rule["title"], "Response plan tested")
        # condition.description got rewritten to the derived requirement.
        self.assertNotIn("TODO", rule["condition"]["description"])
        self.assertIn("Response plan tested", rule["condition"]["description"])
        # framework_control.requirement no longer a TODO.
        self.assertNotIn("TODO", rule["framework_control"]["requirement"])
        # Provenance reflects manual-human (because the source was the rule id, not the pack).
        self.assertEqual(rule["provenance"]["title"], "manual-human")
        self.assertEqual(rule["provenance"]["condition.description"], "manual-human")

    def test_empty_description_and_no_id_leaves_rule_alone(self) -> None:
        """If we have nothing to derive from — neither a description nor a
        usable rule id — return early without filling anything. The rule
        stays as-is and the validator will surface the gap to the user."""
        rule = self._process_check_rule(description="", rule_id="")
        stats = B.enrich_process_check(rule, force=False)
        self.assertEqual(stats["filled"], 0)
        # Title is still TODO.
        self.assertIn("TODO", rule["title"])

    def test_idempotent_on_already_enriched(self) -> None:
        """Re-running enrich_process_check on an already-enriched rule
        should not flip provenance from aws-conformance-pack to manual-human
        or duplicate provenance entries. Lossy idempotency would corrupt
        the audit trail across re-runs."""
        rule = self._process_check_rule(description="Confirm something happens.")
        B.enrich_process_check(rule, force=False)
        title_after_first = rule["title"]
        provenance_after_first = dict(rule["provenance"])
        B.enrich_process_check(rule, force=False)
        self.assertEqual(rule["title"], title_after_first)
        # Provenance unchanged, no duplication.
        self.assertEqual(rule["provenance"], provenance_after_first)

    def test_account_scoped_resource_types_for_process_checks(self) -> None:
        """Process checks attest to organisational state, not a CFN
        resource. Default to AWS::::Account."""
        rule = self._process_check_rule(description="Confirm something.")
        B.enrich_process_check(rule, force=False)
        self.assertEqual(rule["resource_types"], ["AWS::::Account"])


# ---------------------------------------------------------------------------
# enrich_rule integration — pins the snapshot→YAML field map
# ---------------------------------------------------------------------------

class TestEnrichRuleIntegration(unittest.TestCase):
    def test_snapshot_fields_land_at_correct_paths(self) -> None:
        """SNAPSHOT_TO_YAML drives every refresh+enrich. If the table falls
        out of sync with the YAML schema, fields go missing silently —
        validate_yaml will then flag TODOs that bulk_enrich claims to have
        cleared. Pin the canonical mapping."""
        rule = {
            "id": "test-rule",
            "title": "TODO: title",
            "framework_control": {"title": "TODO: fc title", "requirement": "TODO: req"},
            "severity": "TODO",
            "service": "TODO",
            "resource_types": ["TODO: rt"],
            "source": {"type": "aws-config-managed-rule", "identifier": "TEST_RULE", "documentation_url": "TODO: url"},
            "condition": {"description": "TODO: desc", "logic": "TODO: logic"},
            "remediation": {"summary": "TODO: summary"},
        }
        snap = {
            "title": "Real Title",
            "service": "ec2",
            "severity": "HIGH",
            "framework_control_requirement": "Real requirement text from AWS docs",
            "condition_description": "Real condition description",
            "condition_logic": "ec2_instance.MetadataOptions.HttpTokens == 'required'",
            "remediation_summary": "Real remediation steps",
            "documentation_url": "https://docs.aws.amazon.com/config/latest/developerguide/test-rule.html",
            "resource_types": ["AWS::EC2::Instance"],
            "parameters": {},
        }
        stats = B.enrich_rule(rule, snap, force=False)
        # Every snapshot field landed at its YAML path.
        self.assertEqual(rule["title"], "Real Title")
        self.assertEqual(rule["framework_control"]["title"], "Real Title")
        self.assertEqual(rule["framework_control"]["requirement"], "Real requirement text from AWS docs")
        self.assertEqual(rule["severity"], "HIGH")
        self.assertEqual(rule["service"], "ec2")
        self.assertEqual(rule["condition"]["description"], "Real condition description")
        self.assertEqual(rule["condition"]["logic"], "ec2_instance.MetadataOptions.HttpTokens == 'required'")
        self.assertEqual(rule["remediation"]["summary"], "Real remediation steps")
        self.assertEqual(rule["source"]["documentation_url"], "https://docs.aws.amazon.com/config/latest/developerguide/test-rule.html")
        self.assertEqual(rule["resource_types"], ["AWS::EC2::Instance"])
        # Every filled field was tagged with the standard managed-rule provenance.
        for path in ("title", "severity", "service", "framework_control.title",
                     "framework_control.requirement", "condition.description",
                     "condition.logic", "remediation.summary",
                     "source.documentation_url", "resource_types"):
            self.assertEqual(
                rule["provenance"].get(path),
                "aws-config-managed-rule-doc",
                msg=f"{path} provenance not tagged",
            )
        self.assertGreater(stats["filled"], 0)

    def test_legacy_cfn_types_remapped_through_enrich_rule(self) -> None:
        """The end-to-end pin: a snapshot with legacy AWS::OpenSearch::Domain
        must land in the YAML as AWS::OpenSearchService::Domain so
        validate_yaml's CFN-type check passes. This is the layer that broke
        on iter-13 under --force."""
        rule = {
            "id": "test", "title": "TODO", "framework_control": {"requirement": "TODO"},
            "severity": "TODO", "service": "TODO", "resource_types": ["TODO"],
            "source": {"type": "aws-config-managed-rule", "identifier": "X"},
            "condition": {"description": "TODO", "logic": "TODO"},
            "remediation": {"summary": "TODO"},
        }
        snap = {
            "title": "T", "service": "s", "severity": "MEDIUM",
            "framework_control_requirement": "r", "condition_description": "d",
            "condition_logic": "x == y", "remediation_summary": "r",
            "documentation_url": "https://docs.aws.amazon.com/config/latest/developerguide/x.html",
            "resource_types": ["AWS::OpenSearch::Domain", "AWS::ACM::Certificate"],
            "parameters": {},
        }
        B.enrich_rule(rule, snap, force=False)
        self.assertEqual(
            rule["resource_types"],
            ["AWS::OpenSearchService::Domain", "AWS::CertificateManager::Certificate"],
        )

    def test_skip_already_populated_without_force(self) -> None:
        """A field with a real (non-TODO) value survives default bulk_enrich."""
        rule = {
            "id": "test", "title": "Existing curated title",
            "framework_control": {"requirement": "Existing req"},
            "severity": "CRITICAL",
            "service": "ec2",
            "resource_types": ["AWS::EC2::Instance"],
            "source": {"type": "aws-config-managed-rule", "identifier": "X",
                       "documentation_url": "https://existing-url.example.com"},
            "condition": {"description": "Existing", "logic": "x == y"},
            "remediation": {"summary": "Existing remediation"},
        }
        snap = {
            "title": "Snapshot Title", "service": "snapshot-service",
            "severity": "LOW", "framework_control_requirement": "Snapshot req",
            "condition_description": "Snapshot desc", "condition_logic": "snapshot logic",
            "remediation_summary": "Snapshot remediation",
            "documentation_url": "https://snapshot-url.example.com",
            "resource_types": ["AWS::S3::Bucket"], "parameters": {},
        }
        B.enrich_rule(rule, snap, force=False)
        # Curated values survive.
        self.assertEqual(rule["title"], "Existing curated title")
        self.assertEqual(rule["severity"], "CRITICAL")
        self.assertEqual(rule["service"], "ec2")
        self.assertEqual(rule["resource_types"], ["AWS::EC2::Instance"])


# ---------------------------------------------------------------------------
# count_residual_todos — the contract behind --require-zero-todos
# ---------------------------------------------------------------------------

class TestCountResidualTodos(unittest.TestCase):
    def _populated_rule(self) -> dict:
        return {
            "id": "test-rule",
            "title": "Title",
            "framework_control": {"requirement": "req"},
            "severity": "HIGH",
            "service": "ec2",
            "resource_types": ["AWS::EC2::Instance"],
            "source": {"type": "aws-config-managed-rule", "identifier": "X",
                       "documentation_url": "https://example.com"},
            "condition": {"description": "desc", "logic": "x == y"},
            "remediation": {"summary": "remediation"},
            "references": [{"title": "ref", "url": "https://example.com"}],
            "test_cases": [{"name": "case", "input": {}, "expected": "PASS"}],
        }

    def test_zero_for_fully_populated_rule(self) -> None:
        """The READY contract: a fully-enriched rule has no residual TODOs."""
        self.assertEqual(B.count_residual_todos(self._populated_rule()), 0)

    def test_counts_todo_in_top_level_field(self) -> None:
        rule = self._populated_rule()
        rule["severity"] = "TODO: severity"
        self.assertEqual(B.count_residual_todos(rule), 1)

    def test_counts_todo_in_nested_field(self) -> None:
        rule = self._populated_rule()
        rule["condition"]["logic"] = "TODO: logic"
        self.assertEqual(B.count_residual_todos(rule), 1)

    def test_counts_todo_in_list_item(self) -> None:
        rule = self._populated_rule()
        rule["resource_types"] = ["AWS::EC2::Instance", "TODO: another"]
        self.assertEqual(B.count_residual_todos(rule), 1)

    def test_counts_multiple_todos(self) -> None:
        rule = self._populated_rule()
        rule["title"] = "TODO: title"
        rule["framework_control"]["requirement"] = "TODO: req"
        rule["condition"]["logic"] = "TODO: logic"
        self.assertEqual(B.count_residual_todos(rule), 3)

    def test_required_paths_aligns_with_validator(self) -> None:
        """_REQUIRED_PATHS encodes the contract bulk_enrich promises to clear.
        It must mirror validate_yaml's required-fields check, otherwise
        --require-zero-todos says "OK" while the validator says "FAIL".

        Pin the set of paths so future edits don't drift."""
        expected = {
            ("id",),
            ("title",),
            ("framework_control", "requirement"),
            ("severity",),
            ("service",),
            ("resource_types",),
            ("source", "type"),
            ("source", "identifier"),
            ("source", "documentation_url"),
            ("condition", "description"),
            ("condition", "logic"),
            ("remediation", "summary"),
            ("references",),
            ("test_cases",),
        }
        self.assertEqual(set(B._REQUIRED_PATHS), expected)


if __name__ == "__main__":
    unittest.main()
