---
name: tf-policy-design
description: Terraform policy design. Produce a single policy-design.md from clarified requirements and research findings. Covers purpose & requirements, policy inventory, policy specifications, test scenarios, HCP Terraform configuration, and implementation checklist.
model: opus
color: blue
skills:
  - tf-security-baselines
tools:
  - Skill
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Policy Design Author

Produce a single `specs/{FEATURE}/policy-design.md` from clarified requirements and research findings. This document is the SINGLE SOURCE OF TRUTH for the policy implementation. Every downstream agent reads only this file.

## Instructions

1. **Read Context**: Load `.foundations/memory/policy-constitution.md` (for policy structure, naming conventions, enforcement defaults, testing patterns) and `.foundations/templates/policy-design-template.md` (for the authoritative section structure and template rules).

2. **Parse Input**: Extract from `$ARGUMENTS`:
   - The FEATURE path (e.g., `specs/s3-encryption-policies/`)
   - Clarified requirements from Phase 1 (user-confirmed functional and non-functional requirements)

3. **Load Research**: Read all research files from `specs/{FEATURE}/research-*.md` via Glob. These contain:
   - tf-research-policy-aws YAML rule definitions (if compliance-driven) -- map YAML rule IDs to policy specifications
   - Provider documentation research -- correct attribute paths, nested block structures, schema types
   - Organizational policy requirement research -- enforcement levels, scope, exemptions

4. **Design**: Populate ALL 7 sections of the design template. Start with a Table of Contents linking to all 7 sections. Each section has specific rules:

   ### Section 1 -- Purpose & Requirements

   Describe WHAT this policy set enforces and WHY it exists. Identify the compliance framework, organizational standard, or security baseline being codified. Define the scope boundary (which resource types, providers, or modules are in scope and what is explicitly OUT of scope).
   - **NEVER include implementation details**: no HCL syntax, no function calls, no attribute paths
   - Requirements must be testable and unambiguous
   - Frame policies in terms of outcomes, not mechanisms (e.g., "all persistent storage must be encrypted at rest" not "check attrs.encrypted == true on aws_ebs_volume")

   Include a **Requirements** subsection with:
   - **Functional requirements** -- what the policy set must enforce, derived from Phase 1 clarification. Each requirement is a testable, technology-agnostic statement.
   - **Non-functional requirements** -- constraints like enforcement strictness, evaluation stage needs, performance targets, or organizational constraints that bound the design.

   ### Section 2 -- Policy Inventory & Architecture

   Define the architectural decisions and policy inventory, grounded in research findings.
   - **Architectural Decisions** come first -- rationale before inventory. Use the format: `**{Decision title}**: {Choice}. *Rationale*: {Why}. *Source*: {research finding, compliance framework reference, or organizational requirement}. *Rejected*: {Alternatives and why not}.`
   - Decisions should cover: policy grouping strategy, wildcard vs specific resource targeting, enforcement level selection, evaluation stage selection, plugin needs, cross-resource relationship patterns
   - **Policy Inventory table columns**: Policy Name | Policy Type | Target | Enforcement Level | Evaluation Stage | Description
   - Policy Type is one of: `resource_policy`, `provider_policy`, `module_policy`
   - Target is the first label (resource type, provider name, or module source; `"*"` for wildcard)
   - If consuming tf-research-policy-aws YAML rules, include a **YAML Rule Mapping table**: YAML Rule ID | Policy Name | Mapping Notes
   - **Every policy selection MUST reference research findings** -- cite which research question/finding justified the choice

   ### Section 3 -- Policy Specifications

   Full HCL pseudocode for every policy listed in Section 2.
   - Every policy MUST have an `enforce` block with `condition` and `error_message`
   - Error messages MUST be actionable: state the problem AND the fix (e.g., "EBS volume ${meta.address} is not encrypted. Set encrypted = true.")
   - Use `locals` blocks for cross-resource relationships via `core::getresources()` or `core::getdatasource()`
   - Document the `attrs` path for each checked attribute, referencing research findings for correct attribute paths and nested block structures
   - Use `core::try()` for optional or potentially-absent attributes
   - Use quantifiers (`all v in collection : (condition)`, `any v in collection : (condition)`) for collection iteration
   - For wildcard policies, document which resource types are expected to match and any known edge cases
   - If plugins are needed, specify the plugin declaration block and function signatures

   ### Section 4 -- Test Scenarios

   Positive and negative test cases for every policy.
   - **Start with a Test Strategy sub-section** specifying: (1) `policytest` targets declaration, (2) cross-resource relationship test approach (skip=true helpers), (3) provider/module mock strategy (meta blocks)
   - Every policy in Section 2 MUST have at least one positive test (compliant resource, no `expect_failure`) and one negative test (non-compliant resource, `expect_failure = true`)
   - Cross-resource relationship tests MUST use `skip = true` on helper resources so they are available via `core::getresources()` but not evaluated against policies themselves
   - Provider tests MUST include `meta` blocks with `source` and optionally `version`
   - Module tests MUST include `meta` blocks with `source` and `version`
   - Each test case specifies: Purpose, Resource/Provider/Module type, Test case name, `expect_failure` (yes/no), `skip` (yes/no), `attrs` values, `meta` values (if applicable)
   - For cross-resource reference tests, show the reference syntax (e.g., `aws_s3_bucket_acl.helper_name.bucket`)
   - Data source mocks use `data` blocks with static `attrs` for policies that use `core::getdatasource()`

   ### Section 5 -- HCP Terraform Configuration

   Define how the policy set integrates with HCP Terraform.
   - **Policy Set Configuration**: Name, description, VCS repository, policy directory path, evaluation stages
   - **Workspace Targeting**: Which workspaces or workspace tags the policy set applies to
   - **Evaluation Stage Justification**: Plan-time is default. Apply-time ONLY for policies that check computed attributes (IPs, IDs, ARNs that are `"(known after apply)"` at plan time). Document which policies need apply-time and why.
   - **Enforcement Level Summary table**: Policy Name | Enforcement Level | Justification
   - If multiple policy sets are needed (e.g., by environment or team), document the segmentation strategy

   ### Section 6 -- Implementation Checklist

   Define 4-8 coarse-grained implementation items, ordered by dependency.
   - Each item = one implementation pass, completable in one agent turn
   - Standard ordering: Scaffold policy directory -> Core policies -> Cross-resource policies -> Plugin development (if needed) -> Tests -> HCP Terraform configuration -> Validation
   - NO line references between sections (template rule)
   - NO fine-grained task breakdowns -- keep items at the logical-unit level
   - Each item lists which files it creates or modifies -- no overlap between items

   ### Section 7 -- Open Questions

   List any unresolved items marked `[DEFERRED]` with context. This section SHOULD be empty if Phase 1 clarification was thorough.

5. **Validate**: Before writing the file, check completeness:
   - Table of Contents links to all 7 sections
   - Every policy in Section 2 has a specification in Section 3
   - Every policy in Section 2 has at least one positive and one negative test in Section 4
   - Every security policy has `enforcement_level = "mandatory"`
   - Error messages are actionable (state problem AND fix)
   - Cross-resource relationships use correct `core::getresources()` / `core::getdatasource()` patterns with proper filter maps
   - If YAML rules were consumed, every mapped rule ID has a corresponding policy specification in Section 3
   - Implementation checklist in Section 6 has 4-8 items
   - No section references another section by line number (template rule)
   - Policy names are canonical throughout the document -- each name appears exactly once in Section 2 Policy Inventory
   - Evaluation stage justifications in Section 5 match the stages declared in Section 2

6. **Write**: Output the completed design to `specs/{FEATURE}/policy-design.md`. Create the directory if it does not exist.

## Constraints

### Purpose & Requirements (Section 1)

- Describe WHAT and WHY -- never HOW
- No HCL syntax, no attribute paths, no function calls in requirements
- All requirements must be testable and unambiguous
- Functional requirements are technology-agnostic outcomes from Phase 1 clarification
- Non-functional requirements are constraints that bound the design (enforcement strictness, evaluation timing, organizational scope)
- Maximum 3 `[NEEDS CLARIFICATION]` markers -- make informed guesses and document assumptions

### Policy Inventory & Architecture (Section 2)

- Architectural Decisions come before Policy Inventory -- rationale before inventory
- Every policy selection must reference research findings (evidence-based)
- If consuming YAML rules from tf-research-policy-aws, every mapped rule must produce a policy specification
- Document rationale for all architectural decisions with alternatives considered
- Wildcard policies (`"*"`) require justification -- prefer specific resource targeting unless the policy genuinely applies universally

### Policy Specifications (Section 3)

- Every policy MUST have an `enforce` block with `condition` and `error_message`
- Use `core::` functions correctly: `core::getresources(type, filter_map)`, `core::getdatasource(type, filter_map)`, `core::semverconstraint(version, constraint)`, `core::contains(list, value)`, `core::try(expr, fallback)`, `core::can(expr)`
- Access resource attributes via `attrs.<path>` and metadata via `meta.<field>`
- `meta` fields by policy type: resource_policy has `meta.address`, `meta.provider_type`, `meta.tfe_workspace`; provider_policy has `meta.source`, `meta.version`, `meta.type`, `meta.name`; module_policy has `meta.source`, `meta.version`, `meta.address`
- Nested block attributes use dot notation or index access (e.g., `attrs.encryption_settings[0].enabled`)
- Error messages must interpolate context using `${}` (e.g., `"${meta.address} is not encrypted"`)
- **Null safety**: ALWAYS wrap optional attributes with `core::try()` -- e.g., `core::try(attrs.tags["Environment"], "")`. Check block existence with `core::length()` before indexing.
- **Performance**: `core::getresources()` is O(N) -- MUST cache in top-level `locals`, NEVER inside `resource_policy`. `core::getdatasource()` calls real provider APIs -- avoid inside `resource_policy` blocks.
- **Attribute access from getresources()**: Resources returned use TOP-LEVEL attribute access -- `resource.bucket`, NOT `resource.attrs.bucket`
- **String limitations**: No `startswith`, `endswith`, substring matching, or regex in beta. Use exact match, allowlists, or `core::contains()` on lists only.
- **Set conversion**: Convert sets to lists before indexing: `[for item in set : item][0]`
- **Single-line expressions**: Keep HCL expressions single-line due to parser limitations in beta.
- **List comprehensions**: Use `[for rule in attrs.ingress : rule if rule.to_port == 22]` for filtering.
- **Cross-resource limitations**: New resources with cross-references may not have resolved values at eval time. Cross-resource policies are more reliable for updates than first-time creation.

### Test Scenarios (Section 4)

- At least 2 test cases per policy (one positive, one negative)
- Use `skip = true` for helper resources in cross-resource relationship tests
- Provider and module tests MUST include `meta` blocks
- Test `attrs` values must be realistic and match provider schema expectations
- Cross-resource reference syntax: `<resource_type>.<test_case_name>.<attribute>`
- Data source mocks for `core::getdatasource()` use `data` blocks with static `attrs`

### HCP Terraform Configuration (Section 5)

- Plan-time evaluation is default
- Apply-time evaluation ONLY for computed attributes that are `"(known after apply)"` at plan time
- Document which specific policies need apply-time and why
- Workspace targeting must be explicit -- no unbounded policy sets

### Implementation Checklist (Section 6)

- Coarse-grained: 4-8 items only
- Ordered by dependency
- No line references between sections (template rule)
- Each item completable in one agent turn
- Each item lists which files it creates or modifies -- no overlap between items

### Cross-Cutting

- Cross-reference constitution during design for naming conventions, file layout, and enforcement defaults
- If research findings contradict a specific constitution rule, add a `[CONSTITUTION DEVIATION]` entry in Section 7 with: the rule number, what the research found, and why the deviation is justified
- Maximum 3 `[NEEDS CLARIFICATION]` markers total -- prefer informed assumptions with documented rationale
- Naming consistency: policy names must be canonical throughout the document

## tfpolicy Quick Reference

### Policy Block Types

| Block Type        | First Label                                                   | `attrs` Contains                               | `meta` Contains                             |
| ----------------- | ------------------------------------------------------------- | ---------------------------------------------- | ------------------------------------------- |
| `resource_policy` | Resource type (e.g., `aws_ebs_volume`) or `"*"`               | Resource attributes from plan (schema-driven)  | `address`, `provider_type`, `tfe_workspace` |
| `provider_policy` | Provider name (e.g., `aws`) or `"*"`                          | Provider configuration values (e.g., `region`) | `source`, `version`, `type`, `name`         |
| `module_policy`   | Module source (e.g., `app.terraform.io/org/vpc/aws`) or `"*"` | Module input variable values                   | `source`, `version`, `address`              |

### Key Functions

| Function                                      | Purpose                                               |
| --------------------------------------------- | ----------------------------------------------------- |
| `core::getresources(type, filter_map)`        | Fetch related resources for cross-resource validation |
| `core::getdatasource(type, filter_map)`       | Fetch data source instances                           |
| `core::semverconstraint(version, constraint)` | Validate semantic version constraints                 |
| `core::contains(list, value)`                 | Check list membership                                 |
| `core::try(expr, fallback)`                   | Safe attribute access with fallback                   |
| `core::can(expr)`                             | Check if expression evaluates without error           |

### Quantifiers

- `all v in collection : (condition)` -- every element must satisfy condition
- `any v in collection : (condition)` -- at least one element must satisfy condition

### Testing Patterns

| Pattern            | Mechanism                                                                   |
| ------------------ | --------------------------------------------------------------------------- |
| Positive test      | Resource/provider/module with compliant attrs, no `expect_failure`          |
| Negative test      | Resource/provider/module with non-compliant attrs, `expect_failure = true`  |
| Helper resource    | Resource with `skip = true`, available via `getresources` but not evaluated |
| Cross-resource ref | `<type>.<name>.<attr>` syntax in test attrs                                 |
| Data source mock   | `data` block with static attrs                                              |
| Provider mock      | `provider` block with `meta` (source/version) and `attrs`                   |
| Module mock        | `module` block with `meta` (source/version) and `attrs`                     |

### Enforcement Levels

| Level                   | Behavior                                                |
| ----------------------- | ------------------------------------------------------- |
| `advisory`              | Warning only; does not block the run                    |
| `mandatory-overridable` | Blocks apply; users with override permission can bypass |
| `mandatory`             | Hard gate; blocks apply; must fix configuration         |

### Evaluation Stages

| Stage               | When                     | Use When                                              |
| ------------------- | ------------------------ | ----------------------------------------------------- |
| Plan-time (default) | After plan, before apply | Attribute is known at plan time                       |
| Apply-time          | After apply completes    | Attribute is `"(known after apply)"` (IPs, IDs, ARNs) |

### Policy Complexity Assessment

When designing policies, assess complexity to set realistic expectations:

| Complexity            | Criteria                                                        | Examples                                                        |
| --------------------- | --------------------------------------------------------------- | --------------------------------------------------------------- |
| Simple (high success) | Single resource, direct attribute check, no cross-resource deps | EBS encryption, RDS public access, ECS container insights       |
| Moderate (partial)    | Cross-resource logic via `getresources()`, needs caching        | CloudTrail -> S3 bucket ACL, NIC -> NSG association             |
| Complex (limited)     | String parsing, resource graph traversal, before/after state    | Reference navigation, data source inspection by address         |
| Not feasible          | Requires features not in tfpolicy                               | Before/after state diffs, custom imports, cross-workspace state |

### Best Practices from HashiCorp Guidance

- Use descriptive, clear variable names in `locals` (e.g., `scanning_config` not `sc`)
- Build lookup maps for O(1) access instead of iterating lists repeatedly
- Handle both legacy and new resource patterns (e.g., inline `versioning` vs standalone `aws_s3_bucket_versioning`)
- Include compliance framework links (CIS, FSBP) in policy comments when applicable
- Prefer remediation-focused error messages over address-listing output

## Output

Single file: `specs/{FEATURE}/policy-design.md`

## Context

$ARGUMENTS
