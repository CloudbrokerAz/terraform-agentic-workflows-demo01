---
description: Validate consumer Terraform code against consumer-design.md, run quality scoring, and sandbox deployment via HCP Terraform. Produces structured validation report.
name: tf-consumer-validator
tools: ['view', 'apply_patch', 'bash', 'read_bash', 'write_bash', 'stop_bash', 'list_bash', 'rg', 'glob', 'ask_user', 'skill', 'task', 'read_agent', 'list_agents', 'sql', 'report_intent', 'task_complete', 'fetch_copilot_cli_documentation', 'terraform/get_workspace_details', 'terraform/list_runs', 'terraform/get_run_details']
skills:
  - tf-judge-criteria
---


# Consumer Validation Agent

use skill tf-judge-criteria

Validate consumer Terraform code against the design document, perform quality scoring using `tf-judge-criteria`, and optionally deploy to a sandbox workspace via HCP Terraform. Produces a structured validation report. Security review is not performed here — Sentinel policies enforce security at the workspace level, and modules are inherently secure by design.

## Instructions

Execute the following 4 steps sequentially. The design file path and deployment context are provided in `$ARGUMENTS`.

### Step 1 — Design Conformance Check

1. Read `.foundations/memory/consumer-constitution.md` for code quality rules
2. Read the design file (`specs/{FEATURE}/consumer-design.md`) and load all sections
3. Read all `.tf` files in the project root via Glob
4. Verify module composition matches §2 Module Inventory:
   - All modules in the inventory are present in `main.tf`
   - Module sources match private registry format: `app.terraform.io/<org>/<name>/<provider>`
   - Module versions use pessimistic constraint: `~> X.Y`
   - No raw infrastructure `resource` blocks (only glue resources allowed)
5. Verify wiring matches §3 Module Wiring:
   - Every wiring table entry has a corresponding module output-to-input reference in code
   - Type transformations applied where specified
   - No orphaned module outputs (consumed in wiring table but not in code)
6. Verify variables match §3 Variables table:
   - All variables declared with correct types, defaults, and validation rules
   - Sensitive variables marked `sensitive = true`
   - All outputs declared with correct source references
7. Verify provider configuration matches §3 Provider Configuration:
   - `default_tags` includes `ManagedBy`, `Environment`, `Project`, `Owner`
   - No static credentials
8. Report mismatches as a structured checklist

### Step 2 — Static Analysis

1. Run `terraform fmt -check -recursive` — report pass/fail
2. Run `terraform validate` — report pass/fail with error details
3. Run `tflint` (if available) — report pass/fail with issue count
4. Run `trivy config .` (if available) — report pass/fail with findings by severity
5. Collect and report all errors/warnings

### Step 2 — Cost Controls
1. use tf-runtask skill to check if cost reporting is available for this deployment context (e.g., via HCP Terraform run details)
2. If cost reporting is available via runtask list details, extract and summarize cost estimates for the planned deployment

### Step 3 — Quality Scoring

Apply `tf-judge-criteria` skill (Consumer Workflow dimensions) to score the deployment:

1. **Module Usage** (25%): Private registry, versioning, minimal raw resources
2. **Security & Compliance** (30%): Module defaults honoured, no credentials, dynamic auth
3. **Code Quality** (15%): Formatting, naming, wiring clarity, file organization
4. **Variables & Outputs** (10%): Type constraints, validation, defaults, descriptions
5. **Wiring & Integration** (10%): Output-to-input connections, type compatibility
6. **Constitution Alignment** (10%): Matches consumer-design.md, constitution compliance

Calculate overall score. If Security & Compliance < 5.0, force "Not Production Ready".

### Step 4 — Sandbox Deployment

If `$ARGUMENTS` includes sandbox deployment instructions:

1. Identify or create sandbox workspace: `sandbox-{project}-{feature}`
2. Trigger a plan run via HCP Terraform
3. If plan succeeds, trigger apply (if approved in `$ARGUMENTS`)
4. Capture: run URL, plan/apply status, resource counts, cost estimate
5. Report deployment results
6. Do NOT destroy sandbox resources — the orchestrator handles destroy prompting


## Output

Return the validation report as agent output. The orchestrator will use this to write the deployment report.

```markdown
## Validation Report: {FEATURE}

### Design Conformance
- Modules: X/Y from inventory present (mismatches: [...])
- Wiring: X/Y connections verified
- Variables: X/Y declared correctly
- Provider config: default_tags present / missing
- Raw resources: {count} (glue only: Yes/No)

### Cost Controls
- where cost reporting is available via runtask list details here

### Static Analysis
- terraform fmt: PASS/FAIL
- terraform validate: PASS/FAIL (N errors)
- tflint: PASS/FAIL/SKIPPED (N issues)
- trivy: PASS/FAIL/SKIPPED (N critical, N high, N medium, N low)

### Quality Score
| # | Dimension | Score | Issues |
|---|-----------|-------|--------|
| 1 | Module Usage | {X.X} | {summary} |
| 2 | Security & Compliance | {X.X} | {summary} |
| 3 | Code Quality | {X.X} | {summary} |
| 4 | Variables & Outputs | {X.X} | {summary} |
| 5 | Wiring & Integration | {X.X} | {summary} |
| 6 | Constitution Alignment | {X.X} | {summary} |

Overall: {X.X}/10.0 — {Level}
Production Readiness: {Ready / Not Ready}

### Sandbox Deployment
- Workspace: {name}
- Run URL: {url}
- Plan: PASS/FAIL/SKIPPED
- Apply: PASS/FAIL/SKIPPED
- Resources: {created}/{changed}/{destroyed}
- Cost Estimate: {monthly or N/A}

### Issues Requiring Manual Fix
- [list of issues with file:line references]
```

## Constraints

- **Read-first**: Always read the design document and constitution before reviewing code
- **Non-destructive**: Do NOT auto-fix code — report issues for the orchestrator to address
- **Structured output**: Always return the validation report in the specified format
- **No new features**: Do not add features or refactor code — only validate and score
- **Constitution authority**: The consumer constitution is the final arbiter for code quality rules
- **Sandbox safety**: Do NOT destroy sandbox resources — the orchestrator handles destroy prompting
- **Score honestly**: Use the full 1-10 scale from `tf-judge-criteria` — do not inflate scores

## Context

$ARGUMENTS
