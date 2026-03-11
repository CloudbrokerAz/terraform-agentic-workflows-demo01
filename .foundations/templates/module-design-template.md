# Module Design: terraform-{provider}-{name}

**Branch**: feat/{name}
**Date**: {YYYY-MM-DD}
**Status**: Draft | Approved | Implementing | Complete
**Provider**: {provider} >= {version}
**Terraform**: >= {version}

---

## Table of Contents

1. [Purpose & Requirements](#1-purpose--requirements)
2. [Resources & Architecture](#2-resources--architecture)
3. [Interface Contract](#3-interface-contract)
4. [Security Controls](#4-security-controls)
5. [Test Scenarios](#5-test-scenarios)
6. [Implementation Checklist](#6-implementation-checklist)
7. [Open Questions](#7-open-questions)

---

## 1. Purpose & Requirements

{One paragraph. What infrastructure this module creates, who consumes it,
what problem it solves. No implementation details.}

**Scope boundary**: {What is explicitly OUT of scope -- prevents scope creep.}

### Requirements

**Functional requirements** -- what the module must do (from Phase 1 clarification):

- {Testable, technology-agnostic statement of required capability}
- ...

**Non-functional requirements** -- constraints like compliance, performance, availability:

- {Constraint or quality attribute that bounds the design}
- ...

{Requirements bridge Purpose and Architecture. They are testable and unambiguous.
Frame capabilities in terms of outcomes, not resources.}

---

## 2. Resources & Architecture

### Architectural Decisions

{Each decision as a paragraph with this structure:}

**{Decision title}**: {What was chosen}.
*Rationale*: {Why, with MCP research citation if applicable}.
*Rejected*: {What was considered and why it was rejected}.

### Resource Inventory

| Resource Type | Logical Name | Conditional | Depends On | Key Configuration | Schema Notes |
|---------------|-------------|-------------|------------|-------------------|--------------|
| {aws_resource_type} | {this/name} | {variable or "always"} | {resource.name} | {notable settings} | {nested block types: "rule is set", "transition is set", or -- if none} |

---

## 3. Interface Contract

### Inputs

| Variable | Type | Required | Default | Validation | Sensitive | Description |
|----------|------|----------|---------|------------|-----------|-------------|
| {name} | {type} | {Yes/No} | {value or --} | {rule or --} | {Yes/No} | {description} |

{This table is the SINGLE SOURCE OF TRUTH for the module's input interface.
It is not repeated anywhere else in any artifact.}

### Outputs

| Output | Type | Conditional On | Description |
|--------|------|----------------|-------------|
| {name} | {type} | {variable or "always"} | {description} |

---

## 4. Security Controls

| Control | Enforcement | Configurable? | Reference |
|---------|-------------|---------------|-----------|
| Encryption at rest | {how} | {Yes: variable / No: hardcoded} | {CIS/WA control} |
| Encryption in transit | {how} | {Yes/No} | {CIS/WA control} |
| Public access | {how} | {Yes/No} | {CIS/WA control} |
| IAM least privilege | {how} | {Yes/No} | {CIS/WA control} |
| Logging | {how} | {Yes/No} | {CIS/WA control} |
| Tagging | {how} | {Yes/No} | {CIS/WA control} |

{Rules:
- If a control is hardcoded (not configurable), document WHY.
- If it is configurable, the default MUST be the secure option.
- Mark N/A where a domain does not apply, with justification.
- Reference column must cite a CIS AWS Benchmark or AWS Well-Architected control.}

---

## 5. Test Scenarios

{Five scenario groups are required: Secure Defaults, Full Features, Feature Interactions, Validation Errors, and Validation Boundaries.}

### Test Strategy

- **Module source**: Tests run against the **root module directly** — do NOT use `module {}` blocks in `run` blocks. Assert on `resource_type.resource_name.attribute`, not `module.name.resource_type.attribute`.
- **Mock providers**: All test files use `mock_provider` blocks (e.g., `mock_provider "aws" {}`). Add `mock_data` blocks for any `data` sources in the resource inventory.
- **Plan-time limitations**: `command = plan` with mock providers means certain attributes are unknown. This includes: (1) provider-generated values like ARNs, endpoints, and IDs, and (2) cross-resource reference attributes that mock providers cannot resolve (e.g., `.bucket` on `aws_s3_bucket_policy`, `.id` or `.arn` read from a dependent resource). If an attribute's value comes from another resource's computed output or is resolved by the provider during plan, it will be unknown with mocks. Mark such assertions with `[plan-unknown]` below so the test writer can substitute resource-existence checks.

### Scenario: Secure Defaults (basic)

**Purpose**: Verify the module works with minimal inputs and security is enabled by default
**Example**: `examples/basic/`
**Command**: `plan`

**Inputs**:
```hcl
{only required variables -- minimal configuration}
```

**Assertions**:
- {description} — `{HCL access path == expected_value}`
- {description} — `{HCL access path == expected_value}`
- {description} — `{HCL access path}` `[plan-unknown]`
- ...

{Each assertion MUST include the HCL access path that the test writer will use in the assert condition.
Use `one()` for set-typed nested blocks (see Schema Notes in Section 2).
Mark assertions on computed or provider-resolved attributes with `[plan-unknown]` — this includes provider-generated values (ARNs, endpoints, IDs) AND cross-resource references resolved by the provider (e.g., `.bucket`, `.id`, `.arn` on dependent resources).}

### Scenario: Full Features (complete)

**Purpose**: Verify all features enabled, all optional resources created, all outputs populated
**Example**: `examples/complete/`
**Command**: `plan`

**Inputs**:
```hcl
{all features enabled, all optional variables set}
```

**Assertions**:
- {description} — `{HCL access path == expected_value}`
- {description} — `{HCL access path}` `[plan-unknown]`
- {security assertions still hold with all features on}
- ...

### Scenario: Feature Interactions (edge cases)

**Purpose**: Verify non-obvious combinations of feature toggles produce correct behavior. Each sub-scenario tests a specific toggle combination where the interaction matters -- not just "feature on" or "feature off" in isolation.
**Command**: `plan`

{List sub-scenarios. Each sub-scenario is a separate `run` block with its own inputs and assertions.
Focus on combinations where:
- Two toggles interact to gate a resource (e.g., policy requires BOTH website AND public access)
- Disabling a feature should suppress dependent resources
- A feature is present without its typical companion (e.g., CORS without website)
- Default precedence matters (e.g., consumer tags overriding module tags)}

**Sub-scenario: {descriptive name}**
**Inputs**:
```hcl
{specific toggle combination}
```
**Assertions**:
- {description} — `{HCL access path == expected_value}`
- ...

{Repeat for each meaningful toggle combination. Aim for 3-6 sub-scenarios.}

### Scenario: Validation Boundaries (accept)

**Purpose**: Verify validation rules accept values at the valid boundary. Complements the reject cases -- confirms validations do not over-reject.
**Command**: `plan`

**Boundary-pass cases**:
- {input}: {boundary value} -> accepted (description of why this is the boundary)
- ...

{For each validation rule in Section 3, include the minimum valid and/or maximum valid value.
Example: `bucket_name = "abc"` (exactly 3 chars, minimum valid length).
Each case becomes a `run` block with `command = plan` and an assert that the relevant resource is created.}

### Scenario: Validation Errors

**Purpose**: Verify input validation rejects bad inputs

**Expect error cases**:
- {input}: {value} -> {expected error message substring}
- ...

{Rules:
- For security-enforcing resources (policies, encryption, access controls), assert the configuration content, not just existence
- Every assertion becomes exactly one assert block in .tftest.hcl
- Every assertion includes an HCL access path (e.g., `aws_s3_bucket.this.bucket == "my-bucket"`) so the test writer can translate directly to an assert condition
- Use `one()` for set-typed nested blocks — check Schema Notes column in Section 2 to identify which blocks are sets vs lists
- Mark assertions on computed or provider-resolved attributes with `[plan-unknown]` — this includes provider-generated values (ARNs, endpoints, IDs) AND cross-resource reference attributes that mock providers cannot resolve (e.g., `.bucket` on `aws_s3_bucket_policy`, `.id` read from a dependency). The test writer will substitute resource-existence checks
- Every security control from Section 4 must have at least one corresponding assertion here}

---

## 6. Implementation Checklist

- [ ] **A: Scaffold** -- Create file structure, versions.tf, all variables, locals, base resource, core outputs
- [ ] **B: Security core** -- {encryption, access controls, policy -- whatever is security-critical}
- [ ] **C: Feature set** -- {remaining resources, conditional creation}
- [ ] **D: Examples** -- examples/basic/ and examples/complete/
- [ ] **E: Tests** -- .tftest.hcl files from scenarios above
- [ ] **F: Polish** -- README (terraform-docs), formatting, validation, security scan

{Keep this to 4-8 items. Each item = one implementation pass.
NOT a 34-task breakdown. Each item should be completable in one agent turn.
Each item must have clear scope boundaries -- list which files it creates/modifies.
Items must not overlap: if A creates a file, B must not also create that file.}

---

## 7. Open Questions

{Any deferred decisions marked [DEFERRED] with context.
Empty section if all questions resolved during clarification.}

---

## Template Rules

1. No section may reference another section by line number
2. Variable names appear exactly once -- in Interface Contract (Section 3)
3. Resource names appear exactly once -- in Resource Inventory (Section 2)
4. Each test assertion maps 1:1 to a .tftest.hcl assert block and includes the HCL access path
5. Implementation checklist items are coarse-grained -- one per logical unit with explicit file scope
