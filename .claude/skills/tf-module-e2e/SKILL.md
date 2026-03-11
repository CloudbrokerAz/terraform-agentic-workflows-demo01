---
name: tf-module-e2e
description: "Non-interactive test harness for end-to-end Terraform workflow testing. Runs full `/tf-module-plan` -> `/tf-module-implement` cycle with test defaults, bypassing user prompts for automated validation. Pass the prompt filename as the skill argument."
user-invocable: true
argument-hint: "[prompt-file] - Run E2E test from prompts/ directory"
---

# E2E Test Orchestrator

## Workflow

Execute phases sequentially. Before and after each subagent run: post progress to the gh issue. After each subagent run: commit its output to git.

```
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>" "$DETAILS"
```
Valid status values: `started`, `in-progress`, `complete`, `failed`.

## E2E Overrides

Resolve `$PROMPT_FILE` from `$ARGUMENTS` (the prompt filename passed to this skill).

These overrides replace interactive prompts with test defaults:

| Override        | Behavior                                                                    |
| --------------- | --------------------------------------------------------------------------- |
| Requirements    | Read from `.claude/skills/tf-module-e2e/prompts/$PROMPT_FILE`               |
| AskUserQuestion | Use test defaults, do not prompt                                            |
| Approval gates  | Auto-approve, do not wait                                                   |
| Destroy sandbox | Always yes                                                                  |
| Create PR       | No, test artifacts stay on branch                                           |

---

## PART 1: PLANNING

Follow `/tf-module-plan` skill phases with these E2E-specific differences:

- **Phase 1 Setup**: Read requirements from `.claude/skills/tf-module-e2e/prompts/$PROMPT_FILE` instead of gathering from user. Create test issue with `test:e2e` label:
  ```bash
  gh issue create --title "E2E Test: $PROMPT_FILE" --label "test:e2e" --body "$(cat .claude/skills/tf-module-e2e/prompts/$PROMPT_FILE)"
  ```
- **Phase 2 Design**: tf-module-design agent produces `design.md` using test defaults for any decisions; do not use `AskUserQuestion`
- **Phase 3 Summary**: Do NOT add `agent:awaiting-review` label. Do NOT stop for approval. Proceed directly to implementation.

### Planning Artifact Validation

After planning completes, verify the following artifact exists before proceeding:

- `design.md` — consolidated design document (produced by tf-module-design agent)

---

## PART 2: IMPLEMENTATION

Follow `/tf-module-implement` skill phases (TDD-aware, reads design.md) with these E2E-specific differences:

- **Phase 1 Prerequisites**: Use issue number from Part 1. The tf-implement workflow reads `design.md` for implementation guidance.
- **Phase 2 Test Writing**: tf-module-test-writer agent generates test files before implementation code.
- **Phase 3 Implementation**: tf-module-developer agent implements code to pass tests. Commit messages use `test(e2e): implement phase N - <description>`
- **Phase 4 Cleanup**: git push (do NOT create PR). Optionally destroy sandbox resources. Close issue with `test:passed` or `test:failed` label.

### Implementation Test Expectations

After implementation completes, verify these test files exist:

- `tests/basic.tftest.hcl` — basic functionality tests
- `tests/complete.tftest.hcl` — complete integration tests
- `tests/validation.tftest.hcl` — input validation tests

Display: > E2E test complete. Status: [PASSED|FAILED]. See issue #<number> for details.
