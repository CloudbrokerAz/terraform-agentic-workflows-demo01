"""Tests for scripts/summarize_yaml.py.

`summarize_yaml` produces the READY verdict that the eval graders, the
`--require-zero-todos` workflow, and the rest of the skill all use to decide
whether a YAML is shippable. Two bugs in this contract have already shipped
(commit 47b199d "align summarize gap counter with validator"), and the script
itself contains inline commentary about both — counting TODOs in optional
fields (terraform_snippet, framework_control.id) led to false NOT-READY
reports, and the gap counter for unset severity has had subtle drift.

Pin the contract so the next divergence between summarize_yaml and
validate_yaml is a clear test failure rather than a workflow that lies about
deliverability.

Three layers of coverage:

1.  `count_todos` — the field-level counter that must agree with
    validate_yaml.py's required-path check. Test that TODOs in required fields
    count, TODOs in optional/scaffolding fields don't.

2.  `summarize` integration — the whole-doc aggregator: severity histogram,
    gap counts, rules-with-todos rollup. Pin every counter so a refactor can't
    silently miscount.

3.  `is_ready` — the final verdict. The contract is exactly: zero TODOs in
    required paths AND zero unset severities. Custom-rule count must NOT block
    READY (post-bulk_enrich custom rules are first-class deliverables).
"""
from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

THIS = pathlib.Path(__file__).resolve()
SCRIPTS = THIS.parent.parent
sys.path.insert(0, str(SCRIPTS))
import summarize_yaml as S  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers used to build minimal-but-valid rule fixtures
# ---------------------------------------------------------------------------

def _ready_rule(**overrides: object) -> dict:
    """A minimal rule with every required field populated. Override fields to
    test specific gap conditions."""
    base: dict = {
        "id": "test-rule",
        "title": "Title text",
        "framework_control": {
            "id": "CIS 1.1",
            "title": "FC title",
            "requirement": "Plain-English requirement",
        },
        "severity": "MEDIUM",
        "service": "ec2",
        "resource_types": ["AWS::EC2::Instance"],
        "source": {
            "type": "aws-config-managed-rule",
            "identifier": "TEST_RULE",
            "documentation_url": "https://docs.aws.amazon.com/config/latest/developerguide/test-rule.html",
        },
        "condition": {
            "description": "Condition description",
            "logic": "x == y",
        },
        "remediation": {"summary": "Remediation steps"},
        "references": [{"title": "Ref", "url": "https://example.com"}],
        "test_cases": [{"name": "case1", "input": {}, "expected": "PASS"}],
    }
    for k, v in overrides.items():
        base[k] = v
    return base


# ---------------------------------------------------------------------------
# is_todo — string-prefix predicate
# ---------------------------------------------------------------------------

class TestIsTodo(unittest.TestCase):
    def test_starts_with_todo(self) -> None:
        self.assertTrue(S.is_todo("TODO: anything"))
        self.assertTrue(S.is_todo("TODO"))

    def test_leading_whitespace_tolerated(self) -> None:
        """Authors paste indentation sometimes."""
        self.assertTrue(S.is_todo("   TODO: with leading whitespace"))

    def test_real_values_not_todo(self) -> None:
        self.assertFalse(S.is_todo("MEDIUM"))
        self.assertFalse(S.is_todo("Real description"))
        self.assertFalse(S.is_todo(""))

    def test_non_string_not_todo(self) -> None:
        """count_todos walks dicts with mixed value types — None, list, dict
        must not be classified as TODO."""
        self.assertFalse(S.is_todo(None))
        self.assertFalse(S.is_todo(["TODO: in a list"]))
        self.assertFalse(S.is_todo({"key": "TODO"}))
        self.assertFalse(S.is_todo(42))

    def test_todo_substring_not_classified(self) -> None:
        """A description that *mentions* TODO mid-string is not itself a TODO."""
        self.assertFalse(S.is_todo("This rule does not have any TODO items."))


# ---------------------------------------------------------------------------
# count_todos — the contract that must mirror validate_yaml's required check
# ---------------------------------------------------------------------------

class TestCountTodosRequiredFields(unittest.TestCase):
    """Pin every required-field path. A TODO at any of these is a real gap."""

    def test_zero_for_fully_populated_rule(self) -> None:
        self.assertEqual(S.count_todos(_ready_rule()), 0)

    def test_counts_todo_in_id(self) -> None:
        self.assertEqual(S.count_todos(_ready_rule(id="TODO: rule id")), 1)

    def test_counts_todo_in_title(self) -> None:
        self.assertEqual(S.count_todos(_ready_rule(title="TODO: title")), 1)

    def test_counts_todo_in_severity(self) -> None:
        self.assertEqual(S.count_todos(_ready_rule(severity="TODO: severity")), 1)

    def test_counts_todo_in_service(self) -> None:
        self.assertEqual(S.count_todos(_ready_rule(service="TODO: service")), 1)

    def test_counts_todo_in_framework_control_requirement(self) -> None:
        rule = _ready_rule()
        rule["framework_control"]["requirement"] = "TODO: requirement"
        self.assertEqual(S.count_todos(rule), 1)

    def test_counts_todo_in_condition_description(self) -> None:
        rule = _ready_rule()
        rule["condition"]["description"] = "TODO: condition desc"
        self.assertEqual(S.count_todos(rule), 1)

    def test_counts_todo_in_condition_logic(self) -> None:
        rule = _ready_rule()
        rule["condition"]["logic"] = "TODO: condition logic"
        self.assertEqual(S.count_todos(rule), 1)

    def test_counts_todo_in_remediation_summary(self) -> None:
        rule = _ready_rule()
        rule["remediation"]["summary"] = "TODO: remediation"
        self.assertEqual(S.count_todos(rule), 1)

    def test_counts_todo_in_source_documentation_url(self) -> None:
        rule = _ready_rule()
        rule["source"]["documentation_url"] = "TODO: doc url"
        self.assertEqual(S.count_todos(rule), 1)

    def test_counts_todo_in_resource_types_list_item(self) -> None:
        """resource_types is a list — a TODO inside an item still counts."""
        self.assertEqual(
            S.count_todos(_ready_rule(resource_types=["TODO: AWS::Service::Resource"])),
            1,
        )

    def test_multiple_todos_summed(self) -> None:
        rule = _ready_rule(severity="TODO: sev", title="TODO: t")
        rule["condition"]["logic"] = "TODO: l"
        self.assertEqual(S.count_todos(rule), 3)


class TestCountTodosOptionalFields(unittest.TestCase):
    """The regression class behind commit 47b199d ("align summarize gap counter
    with validator"). These fields are NOT required by validate_yaml.py, so
    a TODO in them must not block READY. Counting them previously misled
    workflow runs into reporting NOT READY for files validate_yaml accepted."""

    def test_todo_in_framework_control_id_does_not_count(self) -> None:
        """framework_control.id is optional; the parse layer often leaves
        a `TODO: framework control ID (e.g., CIS 2.3.1)` placeholder."""
        rule = _ready_rule()
        rule["framework_control"]["id"] = "TODO: framework control ID (e.g., CIS 2.3.1)"
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_framework_control_title_does_not_count(self) -> None:
        """framework_control.title is optional too — bulk_enrich populates it
        from rule.title when present, but absence is not a deliverable gap."""
        rule = _ready_rule()
        rule["framework_control"]["title"] = "TODO: control title"
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_terraform_snippet_does_not_count(self) -> None:
        """The most common false-NOT-READY trigger before the fix: parse
        layer inserts `TODO: minimal compliant HCL` into remediation
        scaffolding, summarize used to count it, runs that already passed
        validate_yaml flagged as NOT READY."""
        rule = _ready_rule()
        rule["remediation"]["terraform_snippet"] = "TODO: minimal compliant HCL"
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_aws_cli_snippet_does_not_count(self) -> None:
        rule = _ready_rule()
        rule["remediation"]["aws_cli_snippet"] = "TODO: aws cli command"
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_console_steps_does_not_count(self) -> None:
        rule = _ready_rule()
        rule["remediation"]["console_steps"] = "TODO: console steps"
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_test_case_name_does_not_count(self) -> None:
        """test_cases[] is a required *list*, but test_cases[].name is
        scaffolding metadata. A `TODO: compliant case` placeholder name is
        what parse_conformance_pack writes by default, and it must not block
        READY — only an outright-empty test_cases list does."""
        rule = _ready_rule()
        rule["test_cases"] = [{"name": "TODO: compliant case", "input": {}, "expected": "PASS"}]
        self.assertEqual(S.count_todos(rule), 0)

    def test_todo_in_rule_description_does_not_count(self) -> None:
        """rule.description is optional; only condition.description is required."""
        rule = _ready_rule(description="TODO: optional rule description")
        self.assertEqual(S.count_todos(rule), 0)


class TestCountTodosListSemantics(unittest.TestCase):
    """references and test_cases are required to be NON-EMPTY lists. TODO
    scalars at the surface count; TODOs nested inside item dicts don't (those
    are scaffolding inside optional sub-fields)."""

    def test_todo_string_in_references_list_counts(self) -> None:
        """A bare-string TODO in the references list itself."""
        self.assertEqual(
            S.count_todos(_ready_rule(references=["TODO: at least one reference"])),
            1,
        )

    def test_todo_inside_reference_dict_does_not_count(self) -> None:
        """references[].title is optional inside the dict — a TODO there
        doesn't block validation."""
        rule = _ready_rule(references=[{"title": "TODO: reference title", "url": "https://example.com"}])
        self.assertEqual(S.count_todos(rule), 0)


# ---------------------------------------------------------------------------
# summarize — whole-doc aggregator
# ---------------------------------------------------------------------------

class TestSummarize(unittest.TestCase):
    def _doc(self, *rules: dict, **metadata_overrides: object) -> dict:
        return {
            "metadata": {
                "framework": {"name": "test framework", "version": "1.0"},
                "source": "https://example.com",
                "generated_at": "2026-05-08",
                **metadata_overrides,
            },
            "rules": list(rules),
        }

    def test_severity_histogram_counts_real_severities(self) -> None:
        s = S.summarize(self._doc(
            _ready_rule(severity="HIGH"),
            _ready_rule(severity="HIGH"),
            _ready_rule(severity="MEDIUM"),
            _ready_rule(severity="LOW"),
        ))
        self.assertEqual(s["severity_histogram"]["HIGH"], 2)
        self.assertEqual(s["severity_histogram"]["MEDIUM"], 1)
        self.assertEqual(s["severity_histogram"]["LOW"], 1)
        self.assertEqual(s["totals"]["gap_unset_severity"], 0)

    def test_unset_severity_counted_as_gap(self) -> None:
        """severity is required; a None or TODO value lands in `UNSET` and
        the gap counter increments. Without this, READY would lie."""
        s = S.summarize(self._doc(
            _ready_rule(severity="HIGH"),
            _ready_rule(severity=None),
            _ready_rule(severity="TODO: severity"),
            _ready_rule(severity=""),
        ))
        self.assertEqual(s["severity_histogram"].get("UNSET"), 3)
        self.assertEqual(s["totals"]["gap_unset_severity"], 3)

    def test_service_breakdown(self) -> None:
        s = S.summarize(self._doc(
            _ready_rule(service="ec2"),
            _ready_rule(service="ec2"),
            _ready_rule(service="s3"),
            _ready_rule(service="iam"),
        ))
        self.assertEqual(s["service_breakdown"]["ec2"], 2)
        self.assertEqual(s["service_breakdown"]["s3"], 1)
        self.assertEqual(s["service_breakdown"]["iam"], 1)

    def test_source_type_histogram_includes_custom_rules(self) -> None:
        rule_managed = _ready_rule()
        rule_custom = _ready_rule()
        rule_custom["source"]["type"] = "aws-config-custom-rule"
        s = S.summarize(self._doc(rule_managed, rule_custom, rule_custom))
        self.assertEqual(s["source_type_histogram"]["aws-config-managed-rule"], 1)
        self.assertEqual(s["source_type_histogram"]["aws-config-custom-rule"], 2)

    def test_custom_rule_count_is_informational_not_a_gap(self) -> None:
        """Post-bulk_enrich, AWS_CONFIG_PROCESS_CHECK custom rules are
        first-class — they have severity, condition.logic, remediation.
        gap_custom_rules counts them for visibility but must NOT block READY."""
        rule = _ready_rule()
        rule["source"]["type"] = "aws-config-custom-rule"
        s = S.summarize(self._doc(rule, rule))
        self.assertEqual(s["totals"]["gap_custom_rules"], 2)
        self.assertTrue(S.is_ready(s))

    def test_rules_with_todos_rollup(self) -> None:
        """rules_with_todos is the rule-level rollup; total_todo_placeholders
        is the field-level rollup. They diverge when a single rule has
        multiple TODOs."""
        r_no_todo = _ready_rule()
        r_one_todo = _ready_rule(severity="TODO: sev")
        r_two_todos = _ready_rule(severity="TODO: sev", title="TODO: t")
        s = S.summarize(self._doc(r_no_todo, r_one_todo, r_two_todos))
        self.assertEqual(s["totals"]["rules_with_todos"], 2)
        self.assertEqual(s["totals"]["total_todo_placeholders"], 3)

    def test_rule_count(self) -> None:
        s = S.summarize(self._doc(_ready_rule(), _ready_rule(), _ready_rule()))
        self.assertEqual(s["totals"]["rules"], 3)

    def test_metadata_carried_into_summary(self) -> None:
        """render_text reads framework name + version + source from metadata.
        Pin the carry-through so a future refactor doesn't drop it."""
        s = S.summarize(self._doc(
            _ready_rule(),
            framework={"name": "CIS AWS", "version": "1.4 Level 1"},
        ))
        self.assertEqual(s["metadata"]["framework"]["name"], "CIS AWS")
        self.assertEqual(s["metadata"]["framework"]["version"], "1.4 Level 1")

    def test_empty_rules_list_handled(self) -> None:
        """A doc with metadata but no rules shouldn't crash."""
        s = S.summarize(self._doc())
        self.assertEqual(s["totals"]["rules"], 0)
        self.assertEqual(s["totals"]["rules_with_todos"], 0)
        self.assertTrue(S.is_ready(s))

    def test_non_dict_rules_skipped(self) -> None:
        """Defensive: if YAML deserialization yields a non-dict in rules
        (malformed input), skip rather than crash."""
        s = S.summarize({
            "metadata": {},
            "rules": [_ready_rule(), "not a dict", None, _ready_rule()],
        })
        self.assertEqual(s["totals"]["rules"], 4)  # rules count includes non-dicts
        self.assertEqual(s["totals"]["rules_with_todos"], 0)


# ---------------------------------------------------------------------------
# is_ready — the verdict that gates handoff
# ---------------------------------------------------------------------------

class TestIsReady(unittest.TestCase):
    def test_zero_todos_zero_unset_severity_is_ready(self) -> None:
        s = {"totals": {"total_todo_placeholders": 0, "gap_unset_severity": 0,
                        "rules_with_todos": 0, "gap_custom_rules": 0, "rules": 1}}
        self.assertTrue(S.is_ready(s))

    def test_any_todo_blocks_ready(self) -> None:
        s = {"totals": {"total_todo_placeholders": 1, "gap_unset_severity": 0,
                        "rules_with_todos": 1, "gap_custom_rules": 0, "rules": 1}}
        self.assertFalse(S.is_ready(s))

    def test_unset_severity_blocks_ready(self) -> None:
        s = {"totals": {"total_todo_placeholders": 0, "gap_unset_severity": 1,
                        "rules_with_todos": 0, "gap_custom_rules": 0, "rules": 1}}
        self.assertFalse(S.is_ready(s))

    def test_custom_rules_alone_do_not_block_ready(self) -> None:
        """The contract that took a fix: AWS_CONFIG_PROCESS_CHECK custom rules
        are deliverable post-bulk_enrich. gap_custom_rules > 0 must NOT
        cause is_ready -> False."""
        s = {"totals": {"total_todo_placeholders": 0, "gap_unset_severity": 0,
                        "rules_with_todos": 0, "gap_custom_rules": 5, "rules": 1}}
        self.assertTrue(S.is_ready(s))


# ---------------------------------------------------------------------------
# render_text — surface check that the verdict line is present and correct
# ---------------------------------------------------------------------------

class TestRenderText(unittest.TestCase):
    def _summary(self, **totals_overrides: int) -> dict:
        defaults = {"rules": 1, "rules_with_todos": 0, "total_todo_placeholders": 0,
                    "gap_custom_rules": 0, "gap_unset_severity": 0}
        defaults.update(totals_overrides)
        return {
            "metadata": {"framework": {"name": "test", "version": "1.0"},
                         "source": "https://example.com",
                         "generated_at": "2026-05-08"},
            "totals": defaults,
            "severity_histogram": {"MEDIUM": 1},
            "service_breakdown": {"ec2": 1},
            "source_type_histogram": {"aws-config-managed-rule": 1},
        }

    def test_ready_status_line(self) -> None:
        text = S.render_text(self._summary())
        self.assertIn("Status: READY", text)
        self.assertNotIn("Status: NOT READY", text)

    def test_not_ready_status_line_with_diagnostic(self) -> None:
        """When NOT READY, render_text must report the actual blockers — not
        just "NOT READY", but the counts so the user knows what to fix."""
        text = S.render_text(self._summary(
            total_todo_placeholders=3, rules_with_todos=2, gap_unset_severity=1,
        ))
        self.assertIn("Status: NOT READY", text)
        self.assertIn("3 todos", text)
        self.assertIn("2 rules", text)
        self.assertIn("1 unset severity", text)

    def test_custom_rules_annotated_when_present(self) -> None:
        """gap_custom_rules with annotation explaining it's not a deliverable
        gap. Without this, users panic when they see "5 custom rules"."""
        text = S.render_text(self._summary(gap_custom_rules=5))
        self.assertIn("gap_custom_rules: 5", text)
        self.assertIn("not a deliverable gap", text)


# ---------------------------------------------------------------------------
# main — CLI behaviour incl. --strict exit code
# ---------------------------------------------------------------------------

class TestMain(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = pathlib.Path(self._tmp.name)
        self.yaml_path = self.tmpdir / "rules.yaml"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_yaml(self, doc: dict) -> None:
        import yaml
        self.yaml_path.write_text(yaml.safe_dump(doc), encoding="utf-8")

    def _ready_doc(self) -> dict:
        return {
            "metadata": {"framework": {"name": "t", "version": "1"}},
            "rules": [_ready_rule()],
        }

    def _not_ready_doc(self) -> dict:
        return {
            "metadata": {"framework": {"name": "t", "version": "1"}},
            "rules": [_ready_rule(severity="TODO: sev")],
        }

    def test_strict_exit_zero_when_ready(self) -> None:
        self._write_yaml(self._ready_doc())
        with patch.object(sys, "argv", ["summarize_yaml.py", str(self.yaml_path), "--strict", "--json"]):
            with redirect_stdout(io.StringIO()):
                rc = S.main()
        self.assertEqual(rc, 0)

    def test_strict_exit_one_when_not_ready(self) -> None:
        """--strict is the CI handoff gate — non-zero exit must trigger when
        the YAML can't ship."""
        self._write_yaml(self._not_ready_doc())
        with patch.object(sys, "argv", ["summarize_yaml.py", str(self.yaml_path), "--strict", "--json"]):
            with redirect_stdout(io.StringIO()):
                rc = S.main()
        self.assertEqual(rc, 1)

    def test_default_exit_zero_even_when_not_ready(self) -> None:
        """Without --strict the script is informational — it reports NOT READY
        but exits 0 so callers can chain it."""
        self._write_yaml(self._not_ready_doc())
        with patch.object(sys, "argv", ["summarize_yaml.py", str(self.yaml_path), "--json"]):
            with redirect_stdout(io.StringIO()):
                rc = S.main()
        self.assertEqual(rc, 0)

    def test_json_output_includes_ready_field(self) -> None:
        """The eval graders read the JSON output — pin that the schema
        includes the `ready` boolean derived from is_ready, not just the
        counter totals."""
        self._write_yaml(self._ready_doc())
        buf = io.StringIO()
        with patch.object(sys, "argv", ["summarize_yaml.py", str(self.yaml_path), "--json"]):
            with redirect_stdout(buf):
                rc = S.main()
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("ready", payload)
        self.assertTrue(payload["ready"])
        self.assertIn("totals", payload)


# ---------------------------------------------------------------------------
# REQUIRED_PATHS pin — must align with bulk_enrich and validate_yaml
# ---------------------------------------------------------------------------

class TestRequiredPathsAlignment(unittest.TestCase):
    """Three places encode "fields the validator requires":
      - validate_yaml.py (the validator itself, source of truth)
      - bulk_enrich._REQUIRED_PATHS (drives --require-zero-todos)
      - summarize_yaml.REQUIRED_PATHS (drives the READY verdict)
    Drift between (b) and (c) is the contract bug we're trying to prevent.
    Pin the set so divergence is a clear failure."""

    def test_required_paths_match_bulk_enrich(self) -> None:
        import bulk_enrich
        self.assertEqual(set(S.REQUIRED_PATHS), set(bulk_enrich._REQUIRED_PATHS))


if __name__ == "__main__":
    unittest.main()
