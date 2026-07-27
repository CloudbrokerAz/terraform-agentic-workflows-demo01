---
name: tf-provider-implement
description: SDD Phases 3-4 for provider development. TDD implementation and validation from an existing provider-design-{resource}.md.
user-invocable: true
argument-hint: "[feature-name] [resource-name] - Implement from existing specs/{feature}/provider-design-{resource}.md"
---

# SDD — Provider Implement

Builds and validates a Terraform provider resource from `specs/{FEATURE}/provider-design-{resource}.md` using TDD.

Post progress: `bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>"`. When a phase finishes, post `complete` with the canonical phase name — `Implement` (Phase 3), `Validate` (Phase 4) — so the script ticks the matching box in the issue's Status checklist.
Checkpoint: `bash .foundations/scripts/bash/checkpoint-commit.sh --dir . --prefix feat "<step_name>"`

## Prerequisites

1. **Bootstrap `.foundations`** (no-op when running from the template repo where `.foundations/` already exists): run `LINK="${CLAUDE_PLUGIN_ROOT}/scripts/link-foundations.sh"; [ -f "$LINK" ] && bash "$LINK" || true` to point `.foundations/` at the installed plugin so the repo-relative paths below resolve. Then run `bash .foundations/scripts/bash/validate-env.sh --json` and stop if `gate_passed=false`, and re-check `go version` (Go >= 1.21). Resolve `$FEATURE` from `$ARGUMENTS` or the current git branch name. Resolve `$RESOURCE` from `$ARGUMENTS` only — **the branch name does not encode it** (branches are `NNN-<short-name>`). If it was not supplied, Glob `specs/{FEATURE}/provider-design-*.md` and derive it from the filename; stop and ask if that matches zero or more than one file.
2. Verify `specs/{FEATURE}/provider-design-{resource}.md` exists via Glob. Stop if missing — tell user to run `/tf-provider-plan` first. Capture `$DESIGN_FILE`.
3. Find `$ISSUE_NUMBER` from `$ARGUMENTS` or `gh issue list --search "$FEATURE"`.

## Phase 3: Build + Test

4. Launch concurrent `tf-provider-test-writer` agents with `$DESIGN_FILE`. Verify `_test.go` exists. Checkpoint.
5. Extract all checklist items from design §6 via Grep (`- [ ]` lines).
6. For each item: launch `tf-provider-developer` agent → `go build` + `go test -c` → checkpoint.
7. Final `go vet ./...`. Fix until clean. Verify all §6 items marked `[x]`.

## Phase 4: Validate

8. Launch concurrent `tf-provider-validator` agents with `$DESIGN_FILE` and service directory. If auto-fixes applied, run `go build` to confirm.
9. If remaining issues, launch `tf-provider-developer` targeted at specific issues and re-launch the validator — **max 3 rounds**. If issues remain after round 3, surface the blockers and do NOT proceed to the PR.
10. **Acceptance tests — opt-in, and not run by default.** They provision real cloud resources and cost money, so nothing above triggers them. To run them, re-launch `tf-provider-validator` with `run_acceptance_tests=true` in `$ARGUMENTS` and the provider credentials exported; it runs `TF_ACC=1 go test ./internal/service/<service>/ -run TestAcc -v -timeout 120m`.
    Note that `tf-provider-test-writer` emits every `TestAcc` function with `t.Skip("not implemented")`. A scenario only executes if the developer removed its skip while implementing the matching checklist item, so record in the report which scenarios ran and which are still skipped — a green run with every test skipped is not a passing suite.
11. Write validation report to `specs/{FEATURE}/reports/` using the `tf-report-template` skill provider template.
12. Checkpoint commit, push branch, create PR linking to `$ISSUE_NUMBER`.

## Done

Report: build pass/fail, test compilation, validation status, PR link, and the acceptance-test position — either "not run (default)" or the ran/skipped scenario counts.
