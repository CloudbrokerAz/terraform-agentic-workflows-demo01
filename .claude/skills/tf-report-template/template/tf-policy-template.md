# Validation Report: {{POLICY_SET_NAME}}

| Field             | Value             |
| ----------------- | ----------------- |
| Branch            | {{BRANCH}}        |
| Date              | {{DATE}}          |
| Policy engine     | tfpolicy          |
| Constitution rev  | {{CONSTITUTION_VERSION}} |
| Compliance framework | {{FRAMEWORK or N/A}} |

## tfpolicy validate

**Result**: {{CLEAN / ERRORS}}

```
tfpolicy validate --policies=policies/
```

{{If ERRORS, list each as a bullet: file:line — message}}

## tfpolicy test

**Command**: `tfpolicy test --policies=policies/ --tests=tests/`

| Test File                  | Run Blocks | Passed | Failed | Result        |
| -------------------------- | ---------- | ------ | ------ | ------------- |
| {{file.policytest.hcl}}    | {{N}}      | {{N}}  | {{N}}  | {{PASS/FAIL}} |

**Summary**: {{PASSED}}/{{TOTAL}} run blocks passed across {{FILES}} test files.

### Failures

{{If any failures, list each as: file — run-block name — expected vs actual.
Omit this section if all tests pass.}}

## Design Conformance

| Check                                            | Result        |
| ------------------------------------------------ | ------------- |
| Every policy in design Section 2 exists in code  | {{PASS/FAIL}} |
| Policy names match design Inventory exactly      | {{PASS/FAIL}} |
| Enforcement levels match design Inventory        | {{PASS/FAIL}} |
| Targets (resource/provider/module) match design  | {{PASS/FAIL}} |
| Evaluation stages match design Section 5         | {{PASS/FAIL}} |
| Every policy has at least one pass + one fail test | {{PASS/FAIL}} |
| Implementation checklist (§6) all `[x]`          | {{PASS/FAIL}} |

{{For each FAIL, add a bullet under the table with the specific mismatch.}}

## Compliance Rule Coverage

{{If the design has a Compliance Rule Mapping table, copy its rows here annotated with implementation status. Omit this section if the policy set has no compliance framework mapping.}}

| Rule ID            | Framework  | Policy Name              | Implemented? |
| ------------------ | ---------- | ------------------------ | ------------ |
| {{e.g., CIS 2.1.1}} | {{CIS/NIST/PCI}} | {{policy_name}}    | {{YES/NO}}   |

**Summary**: {{COVERED}}/{{TOTAL}} rules implemented.

## Enforcement Level Summary

| Level                   | Count | Policies          |
| ----------------------- | ----- | ----------------- |
| `mandatory`             | {{N}} | {{names}}         |
| `mandatory_overridable` | {{N}} | {{names}}         |
| `advisory`              | {{N}} | {{names}}         |

{{Flag if any security-critical policy (encryption, public access, IAM, provider/module governance) is below `mandatory` per policy-constitution §5.}}

## Constitution Compliance

Per `.foundations/memory/policy-constitution.md`. Each row = one MUST rule.

| §       | MUST Rule                                                                | Result        |
| ------- | ------------------------------------------------------------------------ | ------------- |
| 1.1     | Files use `.policy.hcl` / `.policytest.hcl` extensions                   | {{PASS/FAIL}} |
| 2.1     | Standard project structure (`policies/`, `tests/`, optional `plugins/`)  | {{PASS/FAIL}} |
| 3.1     | Every `enforce` block has `condition` AND actionable `error_message`     | {{PASS/FAIL}} |
| 3.2     | `enforcement_level` set explicitly on every policy                       | {{PASS/FAIL}} |
| 3.5     | `core::try()` used on optional / nested-block attribute access           | {{PASS/FAIL}} |
| 3.6     | `core::getresources()` cached in top-level `locals` (not inside policies)| {{PASS/FAIL}} |
| 3.6     | `core::getdatasource()` NOT called inside `resource_policy` blocks       | {{PASS/FAIL}} |
| 3.8     | Sets converted to lists before indexing                                  | {{PASS/FAIL}} |
| 4.1     | Every policy has at least one pass + one fail test case                  | {{PASS/FAIL}} |
| 4.2     | Test files declare `policytest { targets = [...] }` explicitly           | {{PASS/FAIL}} |
| 4.3     | Cross-resource helper resources marked `skip = true`                     | {{PASS/FAIL}} |
| 5.x     | Security defaults: encryption/public-access/IAM/governance = `mandatory` | {{PASS/FAIL}} |

{{For each FAIL, add a bullet citing file:line.}}

## Quality Score

| #   | Dimension              | Score   | Issues      |
| --- | ---------------------- | ------- | ----------- |
| 1   | Policy Design          | {{X.X}} | {{summary}} |
| 2   | Security Coverage      | {{X.X}} | {{summary}} |
| 3   | Error Message Quality  | {{X.X}} | {{summary}} |
| 4   | Testing                | {{X.X}} | {{summary}} |
| 5   | Constitution Alignment | {{X.X}} | {{summary}} |
| 6   | HCP Integration        | {{X.X}} | {{summary}} |

**Overall Score**: {{X.X}}/10.0 — {{Level}}
**Production Readiness**: {{Ready / Not Ready}}

{{If Security Coverage (D2) < 5.0, "Not Ready" is forced regardless of overall.}}

## Auto-Fixes Applied

{{Bullet list. Each item: what was fixed + file:line. Empty list is fine.

Allowed auto-fixes (conservative):
- Inserted missing `enforcement_level` from design Section 2 inventory
- Inserted missing `error_message` text from design Section 3 specification
- Inserted missing `policytest { targets = [...] }` header in test files
- Removed orphan `error_message` from non-enforce contexts

Never auto-fix:
- `condition` expressions
- `attrs.<path>` traversals
- Policy logic
- Test assertions}}

## Manual Fixes Required

| Severity | File:Line   | Issue          | Suggested Fix |
| -------- | ----------- | -------------- | ------------- |
| {{P0-P3}} | {{file:line}} | {{description}} | {{guidance}} |

## Overall Status

**{{PASS / FAIL}}**

PASS criteria:

- `tfpolicy validate` clean
- `tfpolicy test` 100% pass
- Design conformance all PASS
- Constitution compliance all PASS
- Security Coverage (D2) ≥ 5.0
- No P0 manual-fix items outstanding

{{If FAIL, list each failing category as a bullet.}}
