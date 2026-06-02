# tf-policy-plan Flow Diagram

Mapping of the `tf-policy-plan` orchestrator skill and its interaction with the `tf-policy-research` and `tf-policy-design` agents. The policy engine is **tfpolicy**.

## Full Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     tf-policy-plan (Orchestrator Skill)                  │
│                           Phases 1 + 2                                  │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  PHASE 1: REQUIREMENTS & RESEARCH                                        │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  Step 1: Run validate-env.sh --json                                │  │
│  │          gate_passed=false? ──Yes──▶ STOP                          │  │
│  │                │ OK                                                │  │
│  │                ▼                                                   │  │
│  │  Step 2: Parse $ARGUMENTS (compliance rule / policy set,           │  │
│  │          provider, description)                                    │  │
│  │          ┌──────────────────────────────────────────────┐          │  │
│  │          │ Compliance-driven? (e.g. cis-aws-3.0-         │          │  │
│  │          │   encryption) → look for existing YAML rules  │          │  │
│  │          │   at policy-research/{framework-slug}*.yaml   │          │  │
│  │          │   from tf-research-policy-aws                 │          │  │
│  │          │ Ad-hoc? (e.g. aws-s3-security) → design from  │          │  │
│  │          │   scratch requirements                        │          │  │
│  │          └──────────────────────────────────────────────┘          │  │
│  │          Ambiguous? ──▶ AskUserQuestion                            │  │
│  │                │                                                   │  │
│  │                ▼                                                   │  │
│  │  Step 3: Create GitHub issue                                       │  │
│  │          - Read issue-body-template.md                             │  │
│  │          - Fill placeholders (policy context — compliance          │  │
│  │            rules enforced, not resources created)                  │  │
│  │          - gh issue create --title "Policy: {rule-or-set}"         │  │
│  │            → capture $ISSUE_NUMBER                                 │  │
│  │          (issue body updated again after Step 6 with               │  │
│  │           enforcement decisions and scope boundaries)              │  │
│  │                │                                                   │  │
│  │                ▼                                                   │  │
│  │  Step 4: create-new-feature.sh --json --workflow policy            │  │
│  │          --issue $ISSUE_NUMBER --short-name "<policy-set-name>"    │  │
│  │          "<feature description>"                                   │  │
│  │          → capture $BRANCH_NAME as $FEATURE and $DESIGN_FILE       │  │
│  │                │                                                   │  │
│  │                ▼                                                   │  │
│  │  Step 5: Scan requirements against tf-domain-category              │  │
│  │          Focus: policy domain classification, enforcement          │  │
│  │          scope, compliance framework alignment                     │  │
│  │                │                                                   │  │
│  │                ▼                                                   │  │
│  │  Step 6: AskUserQuestion (up to 4 questions)                       │  │
│  │          MUST include ALL of:                                      │  │
│  │          ┌──────────────────────────────────────────────┐          │  │
│  │          │ Q1: Security enforcement level — per category│          │  │
│  │          │     mandatory / mandatory-overridable /      │          │  │
│  │          │     advisory?                                │          │  │
│  │          │ Q2: Compliance framework & control family —  │          │  │
│  │          │     CIS / NIST / PCI / custom / none? (if    │          │  │
│  │          │     compliance-driven, YAML rules auto-      │          │  │
│  │          │     consumed)                                │          │  │
│  │          │ Q3: Scope — which resource types, providers, │          │  │
│  │          │     modules? Cross-resource relationship     │          │  │
│  │          │     checks (e.g. CloudTrail → S3 ACL)?       │          │  │
│  │          └──────────────────┬───────────────────────────┘          │  │
│  │                             │                                      │  │
│  │                             ▼                                      │  │
│  │  Step 7: Launch 3-4 CONCURRENT tf-policy-research agents           │  │
│  │          (run in foreground — they use MCP tools)                   │  │
│  │          Wait for all to complete.                                  │  │
│  │          Verify research files exist at                             │  │
│  │          specs/{FEATURE}/research-*.md via Glob.                    │  │
│  │                                                                    │  │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────┐ │  │
│  │  │tf-policy-    │ │tf-policy-    │ │tf-policy-    │ │tf-policy-│ │  │
│  │  │research      │ │research      │ │research      │ │research  │ │  │
│  │  │ (Agent 1)    │ │ (Agent 2)    │ │ (Agent 3)    │ │(Agent 4) │ │  │
│  │  │              │ │              │ │              │ │ optional  │ │  │
│  │  │ Compliance   │ │ Provider     │ │ Enforcement  │ │Cross-    │ │  │
│  │  │ rules        │ │ schemas      │ │ patterns     │ │resource  │ │  │
│  │  │ (YAML)       │ │ (attr paths) │ │              │ │relations │ │  │
│  │  │              │ │              │ │              │ │          │ │  │
│  │  │ INPUT:       │ │ INPUT:       │ │ INPUT:       │ │ INPUT:   │ │  │
│  │  │ 1 question + │ │ 1 question   │ │ 1 question   │ │1 question│ │  │
│  │  │ YAML path    │ │              │ │              │ │          │ │  │
│  │  │              │ │              │ │              │ │          │ │  │
│  │  │ READS:       │ │ MCP calls:   │ │ READS:       │ │ READS:   │ │  │
│  │  │ -policy-     │ │ -get_       │ │ -tf-policy   │ │-provider │ │  │
│  │  │  research/   │ │  provider_  │ │  skill       │ │ schemas  │ │  │
│  │  │  *.yaml      │ │  details    │ │ -search_     │ │          │ │  │
│  │  │ -search_     │ │ (blocks vs  │ │  policies    │ │          │ │  │
│  │  │  policies    │ │  attrs,     │ │              │ │          │ │  │
│  │  │              │ │  plan/apply)│ │              │ │          │ │  │
│  │  │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:      │ │ OUTPUT:  │ │  │
│  │  │ research-    │ │ research-    │ │ research-    │ │research- │ │  │
│  │  │ {slug}.md    │ │ {slug}.md    │ │ {slug}.md    │ │{slug}.md │ │  │
│  │  │ TO DISK      │ │ TO DISK      │ │ TO DISK      │ │TO DISK   │ │  │
│  │  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └────┬─────┘ │  │
│  │         │                │                │              │        │  │
│  │         └────────────────┴────────┬───────┴──────────────┘        │  │
│  │                                   │                               │  │
│  │                    All findings written to disk as                 │  │
│  │                    specs/{FEATURE}/research-{slug}.md              │  │
│  └───────────────────────────────────┬───────────────────────────────┘  │
│                                      │                                  │
│            Orchestrator holds:                                           │
│            - Clarified requirements (from Step 6)                        │
│            - $FEATURE path                                               │
│            - YAML rule path (if compliance-driven)                       │
│            Research files on disk at specs/{FEATURE}/research-*.md       │
│                                      │                                  │
│                                      ▼                                  │
│  PHASE 2: DESIGN                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐  │
│  │                                                                    │  │
│  │  Step 8: Launch tf-policy-design agent                             │  │
│  │  ┌──────────────────────────────────────────────────────────────┐  │  │
│  │  │             tf-policy-design (Agent)                         │  │  │
│  │  │                                                              │  │  │
│  │  │  INPUT (via $ARGUMENTS):                                     │  │  │
│  │  │  - FEATURE path                                              │  │  │
│  │  │  - Clarified requirements                                    │  │  │
│  │  │  - YAML rule path (if compliance-driven)                     │  │  │
│  │  │                                                              │  │  │
│  │  │  READS ITSELF:                                               │  │  │
│  │  │  - specs/{FEATURE}/research-*.md (research findings)         │  │  │
│  │  │  - .foundations/memory/policy-constitution.md                 │  │  │
│  │  │  - .foundations/templates/policy-design-template.md           │  │  │
│  │  │                                                              │  │  │
│  │  │  PRODUCES 7 SECTIONS:                                        │  │  │
│  │  │  ┌────────────────────────────────────────────────────────┐  │  │  │
│  │  │  │ § 1. Purpose & Requirements                            │  │  │  │
│  │  │  │ § 2. Policy Inventory (.policy.hcl files)             │  │  │  │
│  │  │  │ § 3. Policy Specifications (conditions, attrs)        │  │  │  │
│  │  │  │ § 4. Test Scenarios (.policytest.hcl mock blocks)     │  │  │  │
│  │  │  │ § 5. HCP Terraform Configuration (policy sets,        │  │  │  │
│  │  │  │      enforcement levels)                              │  │  │  │
│  │  │  │ § 6. Implementation Checklist                         │  │  │  │
│  │  │  │ § 7. Open Questions                                   │  │  │  │
│  │  │  │                                                        │  │  │  │
│  │  │  │ NOTE: Maps YAML rule IDs → policy specs when a        │  │  │  │
│  │  │  │ compliance framework was consumed.                     │  │  │  │
│  │  │  └────────────────────────────────────────────────────────┘  │  │  │
│  │  │                                                              │  │  │
│  │  │  OUTPUT: specs/{FEATURE}/policy-design.md                    │  │  │
│  │  └──────────────────────────────────────────────────────────────┘  │  │
│  │                         │                                          │  │
│  │                         ▼                                          │  │
│  │  Step 9:  Glob — specs/{FEATURE}/policy-design.md exists?          │  │
│  │           No? → Re-launch tf-policy-design once                    │  │
│  │                         │ Yes                                      │  │
│  │                         ▼                                          │  │
│  │  Step 10: Grep — all 7 sections present?                           │  │
│  │           (## 1. Purpose through ## 7. Open Questions)             │  │
│  │           Missing? → Fix inline                                    │  │
│  │                         │ All present                              │  │
│  │                         ▼                                          │  │
│  │  Step 11: AskUserQuestion — present design summary                 │  │
│  │           ┌─────────────────────────────────────────────┐          │  │
│  │           │ Summary: policy count, enforcement levels   │          │  │
│  │           │ (mandatory/advisory/overridable breakdown), │          │  │
│  │           │ test case count, compliance coverage        │          │  │
│  │           │ (framework + rule count), checklist items   │          │  │
│  │           │                                             │          │  │
│  │           │ Options:                                    │          │  │
│  │           │   [Approve]  [Review file first]  [Changes] │          │  │
│  │           └──────────────────┬──────────────────────────┘          │  │
│  │                              │                                     │  │
│  │                   ┌──────────┼──────────┐                          │  │
│  │                   ▼          ▼          ▼                          │  │
│  │              Approve    Review     Request Changes                  │  │
│  │                 │       file first       │                          │  │
│  │                 │          │    Step 12: Apply changes,             │  │
│  │                 │          │    re-present (loop until approved)    │  │
│  │                 │          └──────────────┘                          │  │
│  │                 ▼                ▼                                  │  │
│  │                 └────────┬───────┘                                  │  │
│  │                          │ APPROVED                                │  │
│  └──────────────────────────┼─────────────────────────────────────────┘  │
│                             │                                            │
│                             ▼                                            │
│  DONE                                                                    │
│  Design approved at specs/{FEATURE}/policy-design.md                     │
│  Run /tf-policy-implement $FEATURE to build.                             │
└──────────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
User prompt (compliance rule or policy set)
    │
    ▼
tf-policy-plan orchestrator
    │
    ├──▶ validate-env.sh (gate)
    │
    ├──▶ Parse arguments (compliance-driven vs ad-hoc)
    │         │
    │         ├── compliance-driven ──▶ locate policy-research/{framework}*.yaml
    │         │                          (from tf-research-policy-aws)
    │         ▼
    ├──▶ AskUserQuestion (enforcement level, framework, scope/cross-resource)
    │         │
    │         ▼
    │    Clarified requirements ─────────────────────────────────┐
    │                                                            │
    ├──▶ 3-4x tf-policy-research agents (concurrent, write to disk)
    │    ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │
    │    │Compliance│ │ Provider │ │Enforcement│ │Cross-    │   │
    │    │ rules    │ │ schemas  │ │ patterns │ │resource  │   │
    │    │ (YAML)   │ │(attr path)│ │          │ │relations │   │
    │    └─────┬────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘   │
    │          └───────────┴────────────┴─────────────┘         │
    │                      │                                     │
    │              Research files: specs/{FEATURE}/research-*.md │
    │                                                            ▼
    ├──▶ tf-policy-design agent ◀──── requirements + $FEATURE + YAML path
    │         │
    │         │  Also reads (itself):
    │         │  - specs/{FEATURE}/research-*.md
    │         │  - policy-constitution.md
    │         │  - policy-design-template.md
    │         │
    │         ▼
    │    specs/{FEATURE}/policy-design.md   ◀── SINGLE OUTPUT ARTIFACT
    │
    ├──▶ Orchestrator verifies (Glob + Grep, never reads content)
    │
    └──▶ User approval gate (AskUserQuestion)
              │
              ▼
         /tf-policy-implement picks up from here
```

## Handoff to tf-policy-implement

```
┌─────────────────┐                                    ┌──────────────────┐
│ tf-policy-plan  │  produces                          │ tf-policy-       │
│ (Phases 1-2)    │ ──────▶ policy-design.md ────────▶ │ implement        │
│                 │         (approved)                  │ (Phases 3-4)     │
└─────────────────┘                                    └──────────────────┘

The ONLY artifact passed between the two skills is:
    specs/{FEATURE}/policy-design.md

Research artifacts (specs/{FEATURE}/research-*.md) persist on disk but are consumed only by the design agent.
```

## Analysis: Policy-Specific Rules

The policy workflow diverges from the module and consumer workflows in several important ways. These differences are non-negotiable constraints baked into the orchestrator skill.

### 1. The Engine is tfpolicy

Policies are authored as `.policy.hcl` and tested as `.policytest.hcl` — not Terraform. If the user asks for a different engine (Sentinel, OPA), the skill redirects them to the constitution and the exception process rather than treating it as a clarification slot.

### 2. Compliance-Driven vs Ad-hoc Inputs

Step 2 branches on the input type. **Compliance-driven** inputs (e.g. `cis-aws-3.0-encryption`) automatically look for existing YAML rule files at `policy-research/{framework-slug}*.yaml` produced by `tf-research-policy-aws`; those rules are consumed by the research and design agents and mapped to policy specifications. **Ad-hoc** inputs (e.g. `aws-s3-security`) are designed from scratch requirements with no framework mapping.

### 3. 7 Design Sections (Test Scenarios Included)

The policy workflow produces a `policy-design.md` with 7 sections — like the module workflow, and unlike the consumer workflow's 6. The policy-specific shape is:

| Section | Policy Workflow                       |
|---------|---------------------------------------|
| 1       | Purpose & Requirements                |
| 2       | Policy Inventory (`.policy.hcl` files) |
| 3       | Policy Specifications                 |
| 4       | **Test Scenarios** (`.policytest.hcl`) |
| 5       | HCP Terraform Configuration           |
| 6       | Implementation Checklist              |
| 7       | Open Questions                        |

Verification at Step 10 checks for 7 sections (`## 1. Purpose` through `## 7. Open Questions`).

### 4. Research Targets Compliance Rules and Provider Schemas

The two anchor research areas are policy-specific: **compliance rules** (reads the YAML rule set, extracting rule IDs, descriptions, resource types, and attribute paths) and **provider schemas** (identifies correct attribute paths for policy conditions, whether each parent is a block — list-shaped, needs `[0]` indexing — or a direct attribute, and plan-time vs apply-time availability per the `tf-policy` blocks-vs-attributes rule).

### 5. Enforcement Level is a First-Class Clarification

Unlike module/consumer security (a controls table), policy clarification Q1 asks for the enforcement level per policy category: `mandatory`, `mandatory-overridable`, or `advisory`. These levels carry through into Section 5 (HCP Terraform Configuration) and govern how the policy set is attached.

### 6. GitHub Issue Uses "Policy:" Prefix

Step 3 creates the issue with `--title "Policy: {compliance-rule-or-policy-set}"`, distinguishing it from module issues (no prefix), consumer issues (`Consumer:`), and provider issues in the issue tracker.
