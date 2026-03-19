---
name: gh-workflow
description: >
  GitHub CLI workflow skill for creating issues, branches, commits, and issue comments — all via the `gh` CLI.
  Use this skill whenever the user wants to interact with GitHub: creating or updating issues, making branches,
  committing and pushing code, commenting on issues or PRs, or any repository management task.
  Trigger on mentions of GitHub issues, branches, commits, PRs, or repository operations.
  Also trigger when users say things like "file an issue", "make a branch for this", "commit this work",
  "post an update", or "push my changes". This skill ensures all GitHub interactions go through the `gh` CLI
  rather than raw git commands or the GitHub API directly.
---

# GitHub CLI Workflow

Every GitHub interaction goes through the `gh` CLI — no `curl`, no direct REST calls, no manual token management. The `gh` CLI handles authentication, pagination, and API versioning for both github.com and GitHub Enterprise.

## Step 0: Environment Check

Run this before any operation. It catches auth problems early and ensures GHE targeting is correct.

```bash
# 1. Verify gh is installed
command -v gh >/dev/null 2>&1 || { echo "gh CLI not found — install from https://cli.github.com"; exit 1; }

# 2. For GitHub Enterprise, GH_HOST MUST be set. Without it, gh targets github.com.
#    Example: export GH_HOST=github.ibm.com
#    This is required for ALL gh commands when working with GHE repos.
if [[ -n "${GH_HOST:-}" ]]; then
  echo "Targeting GitHub Enterprise: ${GH_HOST}"
fi

# 3. Verify authentication
gh auth status
```

If `gh auth status` fails, the user needs to either:
- Run `gh auth login` (interactive)
- Export `GITHUB_TOKEN` (or `GH_ENTERPRISE_TOKEN` for GHE)

## 1. Creating Issues

Use `gh issue create`. Always include `--title`, `--body`, and `--label`. Add `--assignee "@me"` when the creator is also the owner.

```bash
gh issue create \
  --title "Bug: S3 module deprecated ACL parameter" \
  --body "$(cat <<'EOF'
## Summary
The Terraform plan fails because the S3 bucket module uses a deprecated `acl` parameter.

## Steps to Reproduce
1. Run `terraform plan`
2. Observe deprecation error on `aws_s3_bucket.acl`

## Proposed Fix
Remove inline `acl` argument, add `aws_s3_bucket_ownership_controls` resource.
EOF
)" \
  --label "bug"
```

After creation, **capture the issue number** — you need it for branch naming:
```bash
ISSUE_URL=$(gh issue create --title "..." --body "..." --label "bug")
ISSUE_NUMBER=$(echo "$ISSUE_URL" | grep -o '[0-9]*$')
```

### Labels

Labels are a core part of issue management, not an afterthought. Always apply relevant labels at creation time.

**Common label operations:**
```bash
# Apply label(s) at creation
gh issue create --title "..." --body "..." --label "bug" --label "priority:high"

# Add labels to existing issue
gh issue edit 42 --add-label "in-progress"

# Remove a label
gh issue edit 42 --remove-label "needs-triage"

# List available labels in the repo
gh label list
```

**Typical label taxonomy:**
- Type: `bug`, `feature`, `enhancement`, `documentation`
- Priority: `priority:high`, `priority:low`
- Status: `in-progress`, `needs-triage`, `blocked`
- Component: `module:vpc`, `module:s3`

## 2. Creating Branches

Branches linked to issues use the **NNN-short-name** naming convention, where NNN is the zero-padded issue number. This convention is how the team links branches to specs and issues — it is not optional.

**Preferred: `gh issue develop`** — creates the branch and auto-links it to the issue in GitHub's UI:
```bash
PADDED=$(printf "%03d" "$ISSUE_NUMBER")
gh issue develop "$ISSUE_NUMBER" --name "${PADDED}-short-description" --checkout
```

**Fallback** (if `gh issue develop` is unavailable):
```bash
PADDED=$(printf "%03d" "$ISSUE_NUMBER")
BRANCH_NAME="${PADDED}-short-description"
git checkout -b "$BRANCH_NAME"
git push -u origin "$BRANCH_NAME"
```

**Example flow** — create issue then branch in one sequence:
```bash
ISSUE_URL=$(gh issue create --title "Add VPC subnets" --body "..." --label "feature")
ISSUE_NUMBER=$(echo "$ISSUE_URL" | grep -o '[0-9]*$')
PADDED=$(printf "%03d" "$ISSUE_NUMBER")
gh issue develop "$ISSUE_NUMBER" --name "${PADDED}-vpc-subnets" --checkout
```

## 3. Committing Code

Git handles commits; `gh` handles everything that touches the GitHub API.

```bash
# Stage ONLY the specific files that changed — never use git add . or git add -A
git add modules/vpc/main.tf modules/vpc/variables.tf

# Conventional commit message: type(scope): description
git commit -m "feat(vpc): configure 3-AZ subnet layout"

# Push (set upstream on first push)
git push -u origin HEAD
```

**Commit message types:**
- `feat(scope):` — new feature
- `fix(scope):` — bug fix
- `docs(scope):` — documentation change
- `refactor(scope):` — no behavior change
- `build(deps):` — dependency update

**Pre-commit hook retry:** If hooks auto-fix files (terraform fmt, terraform-docs), the commit exits non-zero but the fixes are left on disk. Re-stage and commit again. This function handles it cleanly with `set -e`:
```bash
commit_with_retry() {
  local msg="$1"
  local files=("${@:2}")  # remaining args are file paths
  if git commit -m "$msg"; then return 0; fi
  # Hooks may have auto-fixed files — re-stage and retry once
  git add "${files[@]}"
  git commit -m "$msg"
}
git add modules/vpc/main.tf modules/vpc/variables.tf
commit_with_retry "feat(vpc): configure 3-AZ subnet layout" modules/vpc/main.tf modules/vpc/variables.tf
```

## 4. Commenting on Issues

Use `gh issue comment` for progress updates. Use heredocs when the comment has markdown formatting.

**Simple comment:**
```bash
gh issue comment 42 --body "Starting investigation on the reported problem."
```

**Structured progress comment** — use this template for workflow updates:
```bash
gh issue comment 42 --body "$(cat <<'EOF'
## ✅ Phase: Implementation
**Status**: Complete
**Result**: All modules deployed successfully

**Summary**:
- Configured VPC with 3 availability zones
- Added NAT gateway for private subnet egress
- All 4 success criteria passing
EOF
)"
```

**Status icons:**

| Status | Icon | Template |
|--------|------|----------|
| started | 🔄 | `## 🔄 Phase: <name>` + `**Status**: In Progress` |
| complete | ✅ | `## ✅ Phase: <name>` + `**Status**: Complete` + `**Result**: <summary>` |
| failed | ❌ | `## ❌ Phase: <name>` + `**Status**: Failed` + `**Error**: <what broke>` |

## 5. Closing Issues

Use `gh issue close` with the `--comment` flag to close and explain in a single command. Do not split this into a separate comment + close — the `--comment` flag exists for exactly this purpose.

```bash
# Close with resolution comment — single command
gh issue close 42 --comment "Resolved in PR #55"

# Close as not planned
gh issue close 42 --reason "not planned" --comment "Duplicate of #38"
```

## 6. Targeting a Specific Repo

When operating outside a cloned repo (CI scripts, cross-repo automation), use `--repo` to target explicitly:
```bash
gh issue create --repo "org/repo-name" --title "..." --body "..." --label "bug"
gh issue comment 42 --repo "org/repo-name" --body "Progress update"
gh issue close 42 --repo "org/repo-name" --comment "Done"
```
This is especially common in GHE environments where you may be managing multiple repos.

## 7. Other Common Operations

```bash
# List issues (filter by label, state)
gh issue list --label "bug" --state open

# View issue details
gh issue view 42

# Create a pull request
gh pr create --title "feat: add VPC module" --body "$(cat <<'EOF'
## Summary
- Adds VPC module with 3-AZ subnet layout
- Includes NAT gateway and route tables

## Test plan
- [ ] terraform plan shows expected resources
- [ ] terraform apply succeeds in sandbox
EOF
)"

# Check PR status
gh pr status
gh pr checks
```

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `GH_HOST` | **Yes for GHE** | GitHub Enterprise hostname (e.g., `github.ibm.com`). Without this, `gh` defaults to github.com. |
| `GITHUB_TOKEN` | If no `gh auth login` | Auth token — `gh` picks this up automatically |
| `GH_ENTERPRISE_TOKEN` | GHE alternative | Enterprise-specific token |

## Rules

1. **All GitHub API interactions use `gh`** — never `curl` or direct REST calls.
2. **Stage files explicitly** — `git add <file1> <file2>`, never `git add .` or `git add -A`.
3. **Heredocs for multi-line bodies** — prevents quoting issues, preserves markdown.
4. **Check auth first** — `gh auth status` before any operation.
5. **Capture output** — save issue/PR numbers from creation commands for cross-referencing.
6. **Apply labels at creation** — always include `--label` when creating issues.
7. **Close with `--comment`** — use `gh issue close N --comment "..."`, not separate comment + close.
