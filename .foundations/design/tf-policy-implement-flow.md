# tf-policy-implement Flow Diagram

Mapping of the `tf-policy-implement` orchestrator skill and its interaction with the `tf-policy-test-writer`, `tf-policy-developer`, and `tf-policy-validator` agents. The policy engine is **tfpolicy**, and the build follows **TDD** (tests first).

## Full Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     tf-policy-implement (Orchestrator Skill)         │
│                        Phases 3 + 4                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PREREQUISITES                                                      │
│  ┌───────────────────────────────────────────────────────┐          │
│  │ 1. Resolve $FEATURE from $ARGUMENTS or branch name    │          │
│  │ 2. Run validate-env.sh --json (gate_passed=false?)    │──No──▶ STOP
│  │ 3. Glob: specs/{FEATURE}/policy-design.md exists?     │──No──▶ STOP
│  │    (Tell user to run /tf-policy-plan first)            │          │
│  │ 4. Find $ISSUE_NUMBER from $ARGUMENTS or gh issue list│          │
│  └────────────────────────┬──────────────────────────────┘          │
│                           │ Yes                                     │
│                           ▼                                         │
│  PHASE 3: BUILD + TEST (TDD)                                        │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  Step 5: TEST SCAFFOLD (tests FIRST — TDD red baseline)      │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │          tf-policy-test-writer (Agent)               │    │   │
│  │  │                                                      │    │   │
│  │  │  INPUT: FEATURE path                                 │    │   │
│  │  │  READS: policy-design.md Sections 2 / 3 / 4          │    │   │
│  │  │  WRITES: one tests/*.policytest.hcl per .policy.hcl  │    │   │
│  │  │          in Section 2 inventory (mock blocks)        │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  │          Glob verify tests/*.policytest.hcl (one per policy)  │   │
│  │          Checkpoint commit ("test-scaffold")                 │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 6: BASELINE run                                         │   │
│  │          tfpolicy validate --policies=policies/              │   │
│  │          (skip if policies/ empty — no policies yet)         │   │
│  │          Do NOT run tfpolicy test yet (red baseline:         │   │
│  │          missing-reference, not assertion failure)          │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 7: Grep policy-design.md Section 6 → extract           │   │
│  │          checklist items [A, B, C, D, ...]                   │   │
│  │          (^- \[[ x]\] \*\*[A-F])                             │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 8: FOR EACH unchecked item (declared order):           │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │  ┌──────────────────────────────────────────────┐    │    │   │
│  │  │  │        tf-policy-developer (Agent)           │    │    │   │
│  │  │  │                                              │    │    │   │
│  │  │  │  INPUT: FEATURE=<path> ITEM=<id>: <desc>     │    │    │   │
│  │  │  │  1. Read policy-design.md                     │    │    │   │
│  │  │  │  2. Write/edit .policy.hcl for the item      │    │    │   │
│  │  │  │  3. Mark checklist item [x]                  │    │    │   │
│  │  │  │  OUTPUT: policies/*.policy.hcl               │    │    │   │
│  │  │  └──────────────────────────────────────────────┘    │    │   │
│  │  │                         │                            │    │   │
│  │  │                         ▼                            │    │   │
│  │  │  Orchestrator: tfpolicy validate --policies=policies/│    │   │
│  │  │     Fail? ──▶ re-launch developer w/ error           │    │   │
│  │  │              (max 2 retries per item)                │    │   │
│  │  │  Orchestrator: tfpolicy test (capture counts,        │    │   │
│  │  │     do NOT block yet — later items may still land)   │    │   │
│  │  │  Checkpoint commit ("checklist-item-<id>")           │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  │      (sequential by default — item A scaffolds B/C;          │   │
│  │       concurrent only for non-overlapping file scopes)      │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 9: ALL items landed → final tfpolicy test pass         │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │ run-block still failing?                             │    │   │
│  │  │   policy logic bug  ──▶ re-launch tf-policy-developer │    │   │
│  │  │   fixture wrong     ──▶ re-launch tf-policy-test-     │    │   │
│  │  │                          writer (.policytest.hcl only)│    │   │
│  │  │ Iterate (max 3 rounds across both) until clean        │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 10: Grep — all checklist items [x] in Section 6?      │   │
│  │           (^- \[[ ]\] \*\* must return zero)                 │   │
│  │           Missing? → Mark (if work done) or flag gap         │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                         │                                           │
│                         ▼                                           │
│  PHASE 4: VALIDATE                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Step 11: Launch tf-policy-validator agent                   │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │           tf-policy-validator (Agent)                  │  │   │
│  │  │                                                        │  │   │
│  │  │  1. Design conformance check                           │  │   │
│  │  │     (policies, specs, enforcement vs design)           │  │   │
│  │  │  2. tfpolicy validate --policies=policies/             │  │   │
│  │  │  3. tfpolicy test --policies=policies/ --tests=tests/  │  │   │
│  │  │  4. Quality scoring via Policy Workflow rubric         │  │   │
│  │  │     (tf-judge-criteria, 6 dimensions)                  │  │   │
│  │  │  5. Conservative auto-fix of structural issues         │  │   │
│  │  │                                                        │  │   │
│  │  │  OUTPUT: specs/{FEATURE}/reports/validation_*.md       │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                                                              │   │
│  │  Step 12: Glob report exists? Overall status = FAIL?        │   │
│  │           ──Yes──▶ iterative fix loop:                       │   │
│  │                    - P0/P1 logic/attr → tf-policy-developer  │   │
│  │                    - P0/P1 fixture    → tf-policy-test-writer │   │
│  │                    - re-run validator after each pass        │   │
│  │                    (max 3 validator rounds; still FAIL →     │   │
│  │                     surface to user, do NOT PR)              │   │
│  │           │                                                  │   │
│  │           ▼ PASS                                            │   │
│  │  Step 13: Checkpoint commit ("validation") → push branch    │   │
│  │           → create PR linking $ISSUE_NUMBER                  │   │
│  │           PR title: "Policy: <set-name> (closes #<N>)"      │   │
│  │           PR body: overall status, quality score,           │   │
│  │                    link to validation report                │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                         │                                           │
│                         ▼                                           │
│  DONE: Report tfpolicy validate result, tfpolicy test pass count,   │
│        validator overall status + score, PR link                    │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
policy-design.md ───────────────────────────────────────────────┐
  (§2 inventory, §3 specs, §4 test scenarios, §6 checklist)      │
        │                                                        │
        ▼ (§2/§3/§4)                                             │
  ┌──────────────────────┐                                       │
  │ tf-policy-test-writer│  TDD — tests FIRST                    │
  │ (per .policy.hcl)    │                                       │
  └──────────┬───────────┘                                       │
             ▼                                                   │
   tests/*.policytest.hcl  (mock blocks, red baseline)           │
             │                                                   │
             ▼ (§6 checklist)                                    │
  ┌──────────────────────┐                                       │
  │ tf-policy-developer  │  per checklist item                   │
  └──────────┬───────────┘                                       │
             ▼                                                   │
   policies/*.policy.hcl                                         │
             │                                                   │
             ▼                                                   │
   tf-policy-implement orchestrator                              │
   (tfpolicy validate + test per item, checkpoint commits)      │
             │                                                   │
             ▼                                       policy-design.md ─┘
  ┌──────────────────────┐                          (design conformance)
  │ tf-policy-validator  │
  │ design conformance,  │
  │ tfpolicy validate,   │
  │ tfpolicy test,       │
  │ Policy Workflow rubric│
  │ quality scoring,     │
  │ conservative auto-fix│
  └──────────┬───────────┘
             ▼
   specs/{FEATURE}/reports/validation_*.md
```

## Handoff from tf-policy-plan

```
┌─────────────────┐                                    ┌──────────────────┐
│ tf-policy-plan  │  produces                          │ tf-policy-       │
│ (Phases 1-2)    │ ──────▶ policy-design.md ────────▶ │ implement        │
│                 │         (approved)                  │ (Phases 3-4)     │
└─────────────────┘                                    └──────────────────┘

tf-policy-implement reads only specs/{FEATURE}/policy-design.md as input.
All subagents read their own inputs from disk; the orchestrator never calls
TaskOutput — it verifies artifacts with Glob.
```

## Analysis: Policy-Specific Rules

The policy-implement flow diverges from the module and consumer implement flows in several significant ways, all stemming from the tfpolicy engine and a TDD build order.

### 1. TDD — Tests Written First

Unlike the consumer flow (no test-writer at all), the policy flow launches `tf-policy-test-writer` at Step 5 **before** any policy is authored. Tests give the developer concrete pass/fail signal as it fills the checklist. The design template's Section 6 checklist deliberately does NOT contain a "write tests" item — tests are produced by the scaffold step, not the checklist.

### 2. tfpolicy, Not terraform

The orchestrator runs `tfpolicy validate` and `tfpolicy test` — never `terraform validate`/`terraform test`. Code is `.policy.hcl`; tests are `.policytest.hcl` with mock blocks. There is no `terraform plan`, no sandbox deploy, and no cost estimation.

### 3. Red Baseline is Expected

Step 6 runs `tfpolicy validate` (if `policies/` exists) but explicitly does NOT run `tfpolicy test` at baseline — with no policies yet, tests fail on missing-reference rather than assertion, which is the intended TDD red state. The orchestrator captures it without blocking.

### 4. Two Agents Repair Test Failures

When the final `tfpolicy test` (Step 9) still fails, the orchestrator distinguishes two causes: a **policy logic bug** re-launches `tf-policy-developer`, while a **wrong test fixture** re-launches `tf-policy-test-writer` (which edits `.policytest.hcl` only). The module flow's single developer agent has no equivalent split. Iteration is capped at 3 rounds across both agents.

### 5. Checklist Extraction from Section 6

The policy-design.md checklist lives in Section 6 (the 7-section policy template), not Section 5 (consumer) — Section 4 holds Test Scenarios and Section 5 holds HCP Terraform Configuration. Extraction greps `^- \[[ x]\] \*\*[A-F]`.

### 6. Validator Writes the Report; Enforces the Policy Constitution

`tf-policy-validator` runs the full pipeline (design conformance, `tfpolicy validate`, `tfpolicy test`, Policy Workflow quality scoring, conservative auto-fix) and writes the report to `specs/{FEATURE}/reports/validation_*.md` itself. `.foundations/memory/policy-constitution.md` is the final arbiter for code-quality rules; the validator enforces it and a FAIL status blocks the PR (max 3 fix rounds, then surface to the user).

### 7. PR Uses "Policy:" Title Format

Step 13 creates the PR with title `Policy: <policy-set-name> (closes #<ISSUE_NUMBER>)`, consistent with the issue prefix from the plan phase and distinct from module/consumer/provider PRs.
