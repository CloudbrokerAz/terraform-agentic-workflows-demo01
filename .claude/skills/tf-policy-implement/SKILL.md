---
name: tf-policy-implement
description: SDD Phases 3-4 for tfpolicy. TDD implementation and validation from an existing policy-design.md. Writes tests first, builds policies per checklist item, validates, creates PR. The policy engine is tfpolicy.
user-invocable: true
argument-hint: "[feature-name] - Implement from existing specs/{feature}/policy-design.md"
---

# SDD — Implement (tfpolicy)

Builds and validates a tfpolicy policy set from `specs/{FEATURE}/policy-design.md` using TDD. The policy engine is tfpolicy. If the user pushes for a different engine, redirect them to the constitution and the exception process — do not silently switch.

Post progress at key steps: `bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>"`. Valid status values: `started`, `in-progress`, `complete`, `failed`.
Checkpoint after each phase: `bash .foundations/scripts/bash/checkpoint-commit.sh --dir . --prefix feat "<step_name>"`. The `<step_name>` must be a short hyphenated identifier (e.g., `"test-scaffold"`, `"checklist-item-A"`, `"validation"`) — NOT a sentence or file path.

## Prerequisites

1. Resolve `$FEATURE` from `$ARGUMENTS` or current git branch name.
2. Run `bash .foundations/scripts/bash/validate-env.sh --json`. Stop if `gate_passed=false`.
3. Verify `specs/{FEATURE}/policy-design.md` exists via Glob. Stop if missing — tell user to run `/tf-policy-plan` first.
4. Find `$ISSUE_NUMBER` from `$ARGUMENTS` or `gh issue list --search "$FEATURE"`.

## Phase 3: Build + Test (TDD)

5. **Test scaffold**: Launch `tf-policy-test-writer` agent with FEATURE path. It reads policy-design.md Sections 2/3/4 and writes one `.policytest.hcl` file under `tests/` per `.policy.hcl` in Section 2's inventory. Verify `tests/*.policytest.hcl` exist via Glob — one per policy file. Checkpoint commit (`"test-scaffold"`).

6. **Baseline run**: Run `tfpolicy validate --policies=policies/` if `policies/` exists. If it does not yet (test-writer may have left it empty), skip validate and proceed. Do NOT run `tfpolicy test` here — there are no policies yet, so the tests will error on missing-reference, not on assertion failure. That's the TDD red baseline. Capture the state but do not block.

7. **Extract checklist items**: `grep -E "^- \[[ x]\] \*\*[A-F]" specs/{FEATURE}/policy-design.md` to enumerate Section 6 items. Pull each item's identifier (A, B, C, …), description, and file scope from the markdown.

8. **Iterate the checklist**: For each unchecked item in declared order:
   - Launch `tf-policy-developer` agent with `$ARGUMENTS = "FEATURE=<path> ITEM=<id>: <description>"`.
   - When it completes, run `tfpolicy validate --policies=policies/`. If it fails (and the failure is not the documented hard-block-gate exception), pause and re-launch the developer with the error output as context — max 2 retries per item.
   - Run `tfpolicy test --policies=policies/ --tests=tests/`. Capture pass/fail counts but do NOT block on test failures yet — later items may still need to land. Surface progress.
   - Checkpoint commit (`"checklist-item-<id>"`).
   - Use concurrent subagents only for independent items whose file scopes don't overlap. Item A almost always blocks B/C (scaffolding precedes filling), so default to sequential unless the design clearly separates files.

9. **All items landed — final test pass**: After every checklist item is processed, run `tfpolicy test --policies=policies/ --tests=tests/`. If any run-block still fails, two possibilities:
   - The policy logic has a bug → re-launch `tf-policy-developer` with the failing run-block as context.
   - The test fixture is wrong → re-launch `tf-policy-test-writer` with the failing run-block as context. Test-writer edits `.policytest.hcl` only.
   Iterate (max 3 rounds total across both agents) until `tfpolicy test` is clean.

10. **Checklist verification**: `grep -E "^- \[[ ]\] \*\*" specs/{FEATURE}/policy-design.md` — must return zero results. If any item still `[ ]`, either mark it (if prior items completed its work) or flag the gap before Phase 4.

## Phase 4: Validate

11. Launch `tf-policy-validator` agent with FEATURE path. The validator runs the full pipeline (design conformance, `tfpolicy validate`, `tfpolicy test`, Policy Workflow quality scoring, conservative auto-fix), and writes the validation report to `specs/{FEATURE}/reports/validation_*.md`.

12. Verify the report file exists via Glob. If the validator's overall status is FAIL, drive an iterative fix loop:
    - Re-launch the developer agent for P0 / P1 manual-fix items (logic / attribute path / cross-resource issues).
    - Re-launch the test-writer for P0 / P1 manual-fix items in `.policytest.hcl`.
    - Re-launch the validator after each fix pass.
    - Max 3 validator rounds. If the report is still FAIL after round 3, surface the blocking issues to the user — do NOT proceed to PR with a failing validation.

13. Checkpoint commit (`"validation"`), push branch, create PR linking to `$ISSUE_NUMBER`. PR title format: `Policy: <policy-set-name> (closes #<ISSUE_NUMBER>)`. PR body includes the validator's overall status, quality score, and a link to the validation report file.

## Done

Report: tfpolicy validate result, tfpolicy test pass count, validator overall status + score, PR link.

## Notes

- **TDD ordering is deliberate**: tests are written before policies so the developer has concrete pass/fail signal as it fills in the checklist. The design template's Section 6 checklist does NOT contain a "write tests" item — tests are produced by step 5 above, before iteration starts.
- **Constitution authority**: `.foundations/memory/policy-constitution.md` is the final arbiter for code-quality rules. The validator enforces it. Do not bypass.
- **Subagent context discipline** (per AGENTS.md "Context Management"):
  - Never call `TaskOutput` to read subagent results — every agent writes to disk
  - Verify file existence with Glob after each dispatch
  - Pass only the FEATURE path + scoped question via `$ARGUMENTS`
  - Downstream agents read their own inputs from disk
