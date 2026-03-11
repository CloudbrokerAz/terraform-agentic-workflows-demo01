---
name: tf-implement
description: Implementation orchestrator for Terraform infrastructure provisioning. Drives task execution, sandbox testing, deployment, reporting, and compound learning capture. Entry point for the implementation workflow.
---

# Implementation Orchestrator

## Workflow Steps

- Execute the phases sequentially. Do not move ahead until the step previous has completed within each phase
- Before and after each subagent run: post progress to the gh issue. After each subagent run: commit its output to git.
- use the following template for gh issues:

```
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>" "$DETAILS"
```

### example

```
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "Implementation" "started"
bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "Implementation" "complete" $DETAILS
```

### Phase 1 — Prerequisites

1. Resolve feature directory: `FEATURE_DIR="specs/$(git rev-parse --abbrev-ref HEAD)"`
2. Run validate-env.sh
3. Get issue number from GitHub (search for issue linked to branch or ask user)
4. Verify artifacts exist: `spec.md`, `plan.md`, `tasks.md`, `contracts/module-interfaces.md`

### Phase 2 — Implementation

1. Run mutiple concurrent tf-task-executor subagents (parallel) to execute `tasks.md`and mark completed tasks `[X]` in tasks.md when tasks are done

### Phase 3 — Design Review

1. Run `aws-security-advisor` and `code-quality-judge` subagents in parallel against plan artifacts

### Phase 4 — Sandbox Testing

1. Run `tf-deployer` subagent
2. Capture run URL and deploy status

### Phase 5 — Report

1. Run `tf-report-generator` subagent with run URL and deploy status
2. Gate: report must exist at `specs/<branch>/reports/deployment_*.md`

### Phase 6 — Cleanup + PR

1. git push`and create PR with`gh pr create` linking to issue
2. Post completion comment to issue with PR link
3. Ask user: "Destroy sandbox resources?" — if yes, run destroy via `tf-deployer`

Display: > Implementation complete. PR created and artifacts available in `specs/<branch>/`. Review the deployment report for details.
