---
name: tf-module-implement
description: SDD Phases 3-4. TDD implementation and validation from an existing design.md. Writes tests first, builds module, validates, creates PR.
user-invocable: true
argument-hint: "[feature-name] - Implement from existing specs/{feature}/design.md"
---

# SDD — Implement

Builds and validates a Terraform module from `specs/{FEATURE}/design.md` using TDD.

Post progress at key steps: `bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>"`. Valid status values: `started`, `in-progress`, `complete`, `failed`. When a phase finishes, post `complete` with the canonical phase name — `Implement` (Phase 3), `Validate` (Phase 4) — so the script ticks the matching box in the issue's Status checklist.
Checkpoint after each phase: `bash .foundations/scripts/bash/checkpoint-commit.sh --dir . --prefix feat "<step_name>"`. The `<step_name>` must be a short hyphenated identifier (e.g., `"scaffolding"`, `"checklist-item-1"`, `"validation"`) — NOT a sentence or file path.

## Prerequisites

1. Resolve `$FEATURE` from `$ARGUMENTS` or current git branch name.
2. **Bootstrap `.foundations`** (no-op when running from the template repo where `.foundations/` already exists): run `LINK="${CLAUDE_PLUGIN_ROOT}/scripts/link-foundations.sh"; [ -f "$LINK" ] && bash "$LINK" || true` to point `.foundations/` at the installed plugin so the repo-relative paths below resolve. Then run `bash .foundations/scripts/bash/validate-env.sh --json`. Stop if `gate_passed=false`.
3. Verify `specs/{FEATURE}/design.md` exists via Glob. Stop if missing — tell user to run `/tf-module-plan` first.
4. Find `$ISSUE_NUMBER` from `$ARGUMENTS` or `gh issue list --search "$FEATURE"`.

## Phase 3: Build + Test

5. Launch `tf-module-test-writer` agent with FEATURE path. Verify `versions.tf`, `variables.tf`, and `tests/*.tftest.hcl` exist via Glob.
6. Run `terraform init -backend=false`.
7. Run `terraform validate` to confirm test files and scaffolding are valid HCL. This is the red TDD baseline — tests parse but resources don't exist yet, so `terraform test` will report errors on missing resource references. That is expected. Do NOT run `terraform test` here — it will fail with reference errors, not meaningful assertion failures. Checkpoint commit.
8. Extract checklist items from design.md Section 6 via Grep.
9. For each checklist item:
   - Launch `tf-module-developer` agent with FEATURE path and item description.
   - When it completes, run `terraform validate` and `terraform test`.
   - Checkpoint commit.
   Use concurrent subagents for independent items only when their outputs do not overlap.
10. After all items: run `terraform test`. If failures remain, re-launch `tf-module-test-writer` agent with the error output and any data sources reported by task executors as context.
11. Verify all checklist items in design.md Section 6 are marked `[x]` via Grep. If any remain `[ ]`, either mark them (if the work was done by a prior item) or flag the gap before proceeding.

## Phase 4: Validate

12. Launch `tf-module-validator` agent with FEATURE path. The validator runs the full pipeline (fmt, validate, test, tflint, trivy, terraform-docs), scores quality, auto-fixes unambiguous issues, and writes the validation report to `specs/{FEATURE}/reports/`.
13. Verify the report file exists via Glob. If the validator reports failures, fix iteratively (max 3 rounds) — re-launch the validator after each fix pass.
14. Checkpoint commit, push branch, create PR linking to `$ISSUE_NUMBER`. The PR MUST carry exactly one `semver:*` label — `module_validate.yml` blocks unlabeled PRs and `module_release.yml` uses the label to compute the published version:
    - Ensure the labels exist first (repos created from the template do not inherit labels): `gh label create "semver:patch" --color C2E0C6 --force; gh label create "semver:minor" --color BFD4F2 --force; gh label create "semver:major" --color F9D0C4 --force`.
    - Apply exactly one label at creation: `gh pr create ... --label "semver:<type>"` — `semver:major` for breaking changes to a published module interface, `semver:minor` for new functionality (including the initial module implementation), `semver:patch` for fixes-only changes.

## Done

Report: test pass/fail, validation status, PR link.
