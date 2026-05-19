---
name: tf-policy-plan
description: SDD Phases 1-2. Clarify requirements, research, produce tf-policy-design.md, and await human approval before any code is written. The policy engine is tfpolicy.
user-invocable: true
argument-hint: "[compliance-rule-or-policy-set] [provider] - Compliance rule, framework control, or policy category (e.g., 'cis-aws-3.0-encryption aws', 'nist-800-53-ac aws', 'aws-s3-security aws')"
---

# SDD — tf-policy Plan

Produces `specs/{FEATURE}/tf-policy-design.md` from requirements. Stops for human approval before any code is written.

The policy engine is tfpolicy. If the user asks for a different engine, point them to the constitution and the exception process rather than treating it as a clarification slot.

Post progress at key steps: `bash .foundations/scripts/bash/post-issue-progress.sh $ISSUE_NUMBER "<step>" "<status>" "<summary>"`. Valid status values: `started`, `in-progress`, `complete`, `failed`.
Checkpoint after each phase: `bash .foundations/scripts/bash/checkpoint-commit.sh "<step_name>"`. The `<step_name>` must be a short hyphenated identifier (e.g., `"clarify"`, `"research-and-design"`, `"design-approved"`) — NOT a sentence or file path.

## Phase 1: Requirements & Research

1. Run `bash .foundations/scripts/bash/validate-env.sh --json`. Stop if `gate_passed=false`.
2. Parse `$ARGUMENTS` for the compliance rule or policy grouping, target provider, and description. The input may be:
   - **Compliance-driven**: A framework control or control family (e.g., `cis-aws-3.0-encryption`, `nist-800-53-ac`, `pci-dss-4.0-network`). In this mode, automatically look for existing YAML rules at `policy-research/{framework-slug}*.yaml` from `tf-research-policy-aws`.
   - **Ad-hoc**: A policy category without a compliance framework (e.g., `aws-s3-security`, `provider-governance`). In this mode, policies are designed from scratch requirements.
     Ask via `AskUserQuestion` if the input is ambiguous or incomplete.
3. Create GitHub issue: read `.foundations/templates/issue-body-template.md`, fill in the placeholders with parsed requirements (adapt for policy context — compliance rules enforced, not resources created), and run `gh issue create --title "Policy: {compliance-rule-or-policy-set}" --body "$FILLED_BODY"`. Capture `$ISSUE_NUMBER`. Update the issue body again after Step 6 (clarification) to include enforcement decisions and scope boundaries.
4. Create feature branch: `bash .foundations/scripts/bash/create-new-feature.sh --json --workflow policy --issue $ISSUE_NUMBER --short-name "<policy-set-name>" "<feature description>"`. Parse the JSON output to capture `$BRANCH_NAME` as `$FEATURE` and `$DESIGN_FILE`.
5. Scan requirements against the `tf-domain-category` skill — focus on policy domain classification, enforcement scope, and compliance framework alignment.
6. Ask up to 4 clarification questions via `AskUserQuestion`. Must include:
   - **Security enforcement level**: For each policy category, should enforcement be `mandatory`, `mandatory-overridable`, or `advisory`?
   - **Compliance framework and control family**: Which compliance framework and control family applies (e.g., CIS AWS 3.0 Section 2 — Storage, NIST 800-53 AC — Access Control, PCI DSS 4.0 Requirement 3 — Protect Stored Data, or custom/none)? If compliance-driven, existing YAML rules from `tf-research-policy-aws` are automatically consumed.
   - **Scope**: Which resource types, providers, or modules should the policies target? Are cross-resource relationship checks needed (e.g., CloudTrail -> S3 bucket ACL)?
7. Launch 3-4 concurrent `tf-policy-research` subagents (parallel foreground, NOT `run_in_background`). Each answers ONE question and writes to `specs/{FEATURE}/research-{slug}.md`. Key research areas:
   - **Compliance rules** (`research-compliance-rules`): If a compliance framework was specified and YAML rules exist at `policy-research/{framework-slug}*.yaml`, the agent reads and summarizes the applicable rules — extracting rule IDs, descriptions, resource types, and attribute paths. Include the YAML file path in the agent prompt.
   - **Provider schemas** (`research-provider-schemas`): Research the target provider's resource schemas to identify correct attribute paths for policy conditions and whether each parent is a block (list-shaped, needs `[0]` indexing) or a direct attribute. Note plan-time vs apply-time availability. See the `tf-policy` skill for the blocks-vs-attributes rule.

   Wait for all to complete. Verify research files exist at `specs/{FEATURE}/research-*.md` via Glob.

## Phase 2: Design

8. Launch `tf-policy-design` agent with FEATURE path and clarified requirements. The agent reads the constitution, design template, and research files from `specs/{FEATURE}/research-*.md` itself. If YAML rules from `tf-research-policy-aws` were identified in Step 7, include the YAML file path in the agent prompt so it can map YAML rule IDs to policy specifications in the design sections.
9. Verify `specs/{FEATURE}/policy-design.md` exists via Glob. Re-launch once if missing.
10. Grep to confirm all 7 sections present (`## 1. Purpose` through `## 7. Open Questions`). Fix inline if any missing.
11. Present design summary to user via `AskUserQuestion`: policy count, enforcement levels (mandatory/advisory/overridable breakdown), test case count, compliance coverage (framework + rule count if YAML consumed), checklist items. Options: approve, review file first, request changes.
12. If changes requested, apply and re-present. Repeat until approved.

## Done

Design approved at `specs/{FEATURE}/policy-design.md`. Run `/tf-policy-implement $FEATURE` to build.
