---
name: tf-report-template
description: >
  Deployment report structure, data collection patterns, and section templates
  for Terraform deployment documentation. Preloaded by tf-report-generator agent.
---

# Terraform Deployment Report Patterns

## Report Generation Workflow

1. **Setup**: `BRANCH=$(git branch --show-current); REPORT_FILE="specs/${BRANCH}/reports/deployment_$(date +%Y%m%d-%H%M%S).md"`
2. **Collect**: Architecture, modules, git, HCP, security, tokens, workarounds
3. **Generate**: Read template → Replace `{{PLACEHOLDERS}}` → Validate none remain → Write
4. **Output**: Display path, key metrics, critical issues

## Data Collection Sources

| Data | Source | Method |
|------|--------|--------|
| Architecture | `specs/${BRANCH}/plan.md` | Read file |
| Modules | `*.tf` files | Parse `source =`, classify private vs public |
| Git | `git log`, `git diff` | Bash commands |
| HCP Terraform | MCP tools | `get_workspace_details`, `list_runs`, `get_run_details` |
| Security | `trivy`, `tflint`, `vault-radar` | Bash, parse JSON output |
| Tokens | Agent logs | Sum by phase |
| Workarounds | Code review | Distinguish tech debt vs fixes |

## Critical Report Sections

### Workarounds vs Fixes
Distinguish tech debt (workarounds) from resolved issues (fixes):
- **Workarounds**: What, why, impact, priority, effort for future fix
- **Fixes**: What was fixed, verification method

### Security Analysis
Categorize by severity (Critical/High/Medium/Low):
- File:line reference
- Status: Fixed / Workaround / Not Addressed
- Tool results: terraform validate, trivy, vault-radar

### Module Compliance
- Private registry modules (`app.terraform.io/<org>/`)
- Public modules with justification
- Provider versions with constraints

## Template Location

Use `.foundations/templates/deployment-report-template.md` as the canonical template.

## Validation Checklist

- ✓ No `{{PLACEHOLDER}}` remains (use "N/A" if unavailable)
- ✓ Workarounds documented with priority
- ✓ Security findings complete with severity
- ✓ Module compliance calculated
- ✓ File path displayed to user
- ✓ HCP workspace and run details included
