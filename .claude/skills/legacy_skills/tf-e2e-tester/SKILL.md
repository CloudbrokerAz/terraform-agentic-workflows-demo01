---
name: tf-e2e-tester
description: Non-interactive test harness for end-to-end Terraform workflow testing. Runs full `/tf-plan` → `/tf-implement` cycle with test defaults, bypassing user prompts for automated validation.
args: <prompt-file>
---

# E2E Test Orchestrator

## Workflow Steps

- Execute the phases sequentially. Do not move ahead until the step previous has completed.
- Before and after each subagent run: post progress to the gh issue. After each subagent run: commit its output to git.
- Use the following template for gh issues:

```
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>" "$DETAILS"
```

### example

```
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "Research" "started"
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "Research" "complete" $DETAILS
```

## E2E Overrides

These overrides replace interactive prompts with test defaults:

| Override        | Behavior                                                       |
| --------------- | -------------------------------------------------------------- |
| Requirements    | Read from `.claude/skills/tf-e2e-tester/prompts/<prompt-file>` |
| AskUserQuestion | Use test defaults, do not prompt                               |
| Approval gates  | Auto-approve, do not wait                                      |
| Destroy sandbox | Always yes                                                     |
| Create PR       | No, test artifacts stay on branch                              |

---

## PART 1: PLANNING (from /tf-plan)

### Phase 1 — Setup

- Run validate-env.sh
- Check for error and stop if pre-requisites not met
- Then call MCP `list_terraform_orgs` to verify TFE_TOKEN.
- **E2E Override**: Read requirements from `.claude/skills/tf-e2e-tester/prompts/<prompt-file>` instead of gathering from user
- Create test issue with `test:e2e` label:
  ```bash
  gh issue create --title "E2E Test: <prompt-file>" --label "test:e2e" --body "$(cat .claude/skills/tf-e2e-tester/prompts/<prompt-file>)"
  ```

### Phase 2 — Specification (sequential)

1. sdd-specify → `spec.md`
2. sdd-checklist against `spec.md` → checklist findings
3. sdd-clarify with checklist findings + `spec.md`. **E2E Override**: Use test defaults for HIGH-impact gaps, do not use `AskUserQuestion`

### Phase 3 — Research + Planning (sequential)

1. sdd-research (parallel) → research findings
2. sdd-plan-draft → `plan.md`, `data-model.md`, `contracts/module-interfaces.md`

### Phase 4 — Tasks + Analysis (sequential)

1. sdd-tasks → `tasks.md`
2. sdd-analyze with `tasks.md` → `analysis.md`

### Phase 5 — Summary (no approval wait)

- Compile results, post to GitHub issue
- **E2E Override**: Do NOT add agent:awaiting-review label. Do NOT stop for approval. Proceed directly to implementation.

---

## PART 2: IMPLEMENTATION (from /tf-implement)

### Phase 1 — Prerequisites

- Use issue number from Part 1
- Verify artifacts exist in `$FEATURE_DIR`: `spec.md`, `plan.md`, `tasks.md`, `contracts/module-interfaces.md`

### Phase 2 — Implementation (sequential by phase)

For each phase in `tasks.md`:

1. tf-task-executor with phase tasks + `plan.md` + `contracts/module-interfaces.md`
2. Mark completed tasks `[X]` in tasks.md
3. Commit: `test(e2e): implement phase N - <description>`

### Phase 3 — Design Review

- Run `aws-security-advisor` and `code-quality-judge` subagents in parallel against plan artifacts

### Phase 4 — Sandbox Testing

- Run `tf-deployer` subagent
- Capture run URL and deploy status

### Phase 5 — Report

- Run `tf-report-generator` subagent with run URL and deploy status
- Gate: report must exist at `specs/<branch>/reports/deployment_*.md`

### Phase 6 — Cleanup

- git push (do NOT create PR)
- Post completion comment to issue
- **E2E Override**: Always destroy sandbox resources via `tf-deployer`
- Close issue with `test:passed` or `test:failed` label

Display: > E2E test complete. Status: [PASSED|FAILED]. See issue #<number> for details.
