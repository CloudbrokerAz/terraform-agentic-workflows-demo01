# tf-module-implement Flow Diagram

Mapping of the `tf-module-implement` orchestrator skill and its interaction with the `tf-module-test-writer` and `tf-module-developer` agents.

## Full Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                     tf-module-implement (Orchestrator Skill)               │
│                        Phases 3 + 4                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  PREREQUISITES                                                      │
│  ┌───────────────────────────────────────────────┐                  │
│  │ 1. Resolve $FEATURE                           │                  │
│  │ 2. Run validate-env.sh                        │                  │
│  │ 3. Glob: specs/{FEATURE}/design.md exists?    │──No──▶ STOP     │
│  │ 4. Find $ISSUE_NUMBER                         │                  │
│  └──────────────────────┬────────────────────────┘                  │
│                         │ Yes                                       │
│                         ▼                                           │
│  PHASE 3: BUILD + TEST                                              │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │  Step 5: Launch tf-module-test-writer agent                         │   │
│  │  ┌────────────────────────────────────────────────────────┐  │   │
│  │  │           tf-module-test-writer (Agent)                        │  │   │
│  │  │                                                        │  │   │
│  │  │  INPUT:  design.md Sections 2, 3, 5                    │  │   │
│  │  │                                                        │  │   │
│  │  │  1. Read design.md                                     │  │   │
│  │  │  2. Write versions.tf  (provider constraints)          │  │   │
│  │  │  3. Write variables.tf (interface contract)            │  │   │
│  │  │  4. Write tests/basic.tftest.hcl                       │  │   │
│  │  │  5. Write tests/complete.tftest.hcl                    │  │   │
│  │  │  6. Write tests/edge_cases.tftest.hcl                  │  │   │
│  │  │  7. Write tests/validation.tftest.hcl                  │  │   │
│  │  │                                                        │  │   │
│  │  │  OUTPUT: versions.tf, variables.tf, tests/*.tftest.hcl │  │   │
│  │  └────────────────────────────────────────────────────────┘  │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 6: terraform init -backend=false                       │   │
│  │  Step 7: terraform validate  (RED baseline — tests parse,    │   │
│  │          resources don't exist yet. Do NOT run terraform     │   │
│  │          test here.) Checkpoint commit.                      │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 8: Grep design.md Section 6 → extract checklist items  │   │
│  │          [A, B, C, D, ...]                                   │   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 9: FOR EACH checklist item:                            │   │
│  │  ┌──────────────────────────────────────────────────────┐    │   │
│  │  │  ┌──────────────────────────────────────────────┐    │    │   │
│  │  │  │       tf-module-developer (Agent)                │    │    │   │
│  │  │  │                                              │    │    │   │
│  │  │  │  INPUT:  design.md + checklist item desc     │    │    │   │
│  │  │  │                                              │    │    │   │
│  │  │  │  1. Read design.md (Sections 2, 3, 4)       │    │    │   │
│  │  │  │  2. Read existing .tf files                  │    │    │   │
│  │  │  │  3. Research via MCP (provider/AWS docs)     │    │    │   │
│  │  │  │  4. Write/edit .tf files                     │    │    │   │
│  │  │  │  5. terraform fmt                            │    │    │   │
│  │  │  │  6. terraform validate                       │    │    │   │
│  │  │  │  7. terraform test → report pass/fail        │    │    │   │
│  │  │  │  8. Mark [x] in design.md Section 6         │    │    │   │
│  │  │  │                                              │    │    │   │
│  │  │  │  OUTPUT: Modified .tf files + report         │    │    │   │
│  │  │  └──────────────────────────────────────────────┘    │    │   │
│  │  │                         │                            │    │   │
│  │  │                         ▼                            │    │   │
│  │  │  Orchestrator: terraform validate + terraform test   │    │   │
│  │  │  Checkpoint commit                                   │    │   │
│  │  └──────────────────────────────────────────────────────┘    │   │
│  │              (repeat for each item; concurrent if independent)│   │
│  │                         │                                    │   │
│  │                         ▼                                    │   │
│  │  Step 10: terraform test (final)                             │   │
│  │           Failures? ──Yes──▶ Re-launch tf-module-test-writer with   │   │
│  │                              error output + data source info  │   │
│  │           │                                                  │   │
│  │           ▼ No                                               │   │
│  │  Step 11: Grep: all checklist items [x]?                     │   │
│  │           Missing? → Mark or flag                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                         │                                           │
│                         ▼                                           │
│  PHASE 4: VALIDATE                                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Step 12 (all parallel):                                     │   │
│  │    terraform test                                            │   │
│  │    terraform validate                                        │   │
│  │    terraform fmt -check -recursive                           │   │
│  │    trivy config .                                            │   │
│  │    terraform-docs markdown . > README.md                     │   │
│  │                                                              │   │
│  │  Step 13: Fix failures (max 3 rounds)                        │   │
│  │  Step 14: Write validation report to specs/{FEATURE}/reports/│   │
│  │  Step 15: Checkpoint commit → push branch → create PR        │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                         │                                           │
│                         ▼                                           │
│  DONE: Report test pass/fail, validation status, PR link            │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
design.md ──────────────┬──────────────────────────────────────┐
  (Sections 2, 3, 5)    │              (Sections 2, 3, 4, 6)   │
                         ▼                                      ▼
               ┌─────────────────┐              ┌──────────────────────┐
               │ tf-module-test-writer  │              │  tf-module-developer    │
               │                 │              │  (per checklist item)│
               └────────┬────────┘              └──────────┬───────────┘
                        │                                  │
                        ▼                                  ▼
              versions.tf                          main.tf, outputs.tf
              variables.tf                         (edits to existing .tf)
              tests/*.tftest.hcl
                        │                                  │
                        └──────────┬───────────────────────┘
                                   ▼
                        tf-module-implement orchestrator
                        (validates, tests, commits)
```

## Analysis: Does the Flow Make Sense?

**Yes, the flow is sound.** It correctly implements the TDD cycle from AGENTS.md principles P2 and P5.

### What's Right

1. **Test-first ordering (P2)**: tf-module-test-writer runs before any tf-module-developer. Tests and scaffolding exist before implementation code. The RED baseline at step 7 confirms tests parse but nothing passes yet.

2. **Single artifact (P1)**: Everything flows from `design.md`. No intermediate files are created between agents.

3. **Agent single-responsibility (P5)**: tf-module-test-writer reads design and produces tests + scaffolding. tf-module-developer reads design + checklist item and produces .tf code. Clean separation.

4. **Orchestrator directs, doesn't accumulate (P6)**: tf-module-implement checks file existence via Glob, passes file paths and item descriptions to agents, and runs validation commands. It doesn't read/merge agent outputs.

5. **Fix cycle at step 10**: If tests still fail after all items, tf-module-test-writer is re-launched with error context. This handles the case where task executors introduce data sources that tests didn't originally mock.

### One Tension Worth Noting

The tf-module-developer runs `terraform test` internally (its step 7), and then the orchestrator *also* runs `terraform validate + terraform test` after the executor returns (orchestrator step 9). This is redundant but harmless — the orchestrator's run acts as a trust-but-verify gate. The executor's internal run gives it feedback to self-correct within its own scope, while the orchestrator's run is the authoritative check. This is consistent with P6 (orchestrator verifies state, doesn't trust agent reports blindly).
