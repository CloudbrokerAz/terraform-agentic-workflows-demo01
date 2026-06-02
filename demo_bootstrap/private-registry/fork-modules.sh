#!/usr/bin/env bash
# Fork the top public terraform-aws-modules repos into your GitHub org, skipping
# any module that already exists in the designated HCP Terraform private
# registry (or already exists as a fork).
#
# Terraform/tfe cannot fork GitHub repos, so this covers the gap before
# `terraform apply` publishes the forks into the HCP private registry.
#
# Usage:
#   GITHUB_ORG=hashi-demos-apj HCP_ORG=hashi-demos-apj TFE_TOKEN=... ./fork-modules.sh
#   ./fork-modules.sh hashi-demos-apj
#   ./fork-modules.sh --dry-run hashi-demos-apj
#
# Flags:
#   -n, --dry-run  report what would be forked/skipped; make no changes
#   -h, --help     show this help
#
# Env:
#   GITHUB_ORG     target GitHub org for the forks (or pass as the positional arg)
#   HCP_ORG        HCP Terraform org whose private registry is checked
#                  (defaults to GITHUB_ORG)
#   TFE_TOKEN      HCP Terraform token used for the registry check
#   TFE_HOSTNAME   HCP/TFE hostname (default app.terraform.io)
#   SOURCE_ORG     upstream org to fork from (default terraform-aws-modules)
#   PUBLISH_BRANCH branch each fork is published from; created on the fork from
#                  its default branch if missing (default main; keep in sync
#                  with var.branch). Upstream terraform-aws-* repos default to
#                  master, so this reconciles the master/main gap.
#
# Requires: gh (authenticated with repo write), curl, jq.
set -euo pipefail

DRY_RUN=false
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    -n | --dry-run) DRY_RUN=true ;;
    -h | --help)
      sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    -*)
      echo "ERROR: unknown option: $1" >&2
      exit 1
      ;;
    *) POSITIONAL+=("$1") ;;
  esac
  shift
done

GITHUB_ORG="${POSITIONAL[0]:-${GITHUB_ORG:-}}"
HCP_ORG="${HCP_ORG:-$GITHUB_ORG}"
TFE_HOSTNAME="${TFE_HOSTNAME:-app.terraform.io}"
SOURCE_ORG="${SOURCE_ORG:-terraform-aws-modules}"
PUBLISH_BRANCH="${PUBLISH_BRANCH:-main}" # keep in sync with var.branch in variables.tf

if [ -z "$GITHUB_ORG" ]; then
  echo "ERROR: target org not set. Pass as arg or set GITHUB_ORG." >&2
  exit 1
fi

$DRY_RUN && echo "DRY RUN — no forks will be created."

# Keep this list in sync with var.module_repos in variables.tf.
MODULES=(
  terraform-aws-vpc
  terraform-aws-security-group
  terraform-aws-sqs
  terraform-aws-sns
  terraform-aws-lambda
  terraform-aws-iam
  terraform-aws-cloudwatch
  terraform-aws-ec2-instance
  terraform-aws-autoscaling
  terraform-aws-alb
  terraform-aws-cloudfront
  terraform-aws-s3-bucket
)

# --- Pre-fetch the modules already in the HCP private registry ---------------
# Builds a newline-delimited set of "<name>/<provider>" (e.g. "vpc/aws").
EXISTING_MODULES=""
if [ -n "${TFE_TOKEN:-}" ]; then
  echo "Checking existing modules in ${TFE_HOSTNAME} org ${HCP_ORG}..."
  page=1
  while :; do
    resp="$(curl -fsS \
      -H "Authorization: Bearer ${TFE_TOKEN}" \
      -H "Content-Type: application/vnd.api+json" \
      "https://${TFE_HOSTNAME}/api/v2/organizations/${HCP_ORG}/registry-modules?page%5Bnumber%5D=${page}&page%5Bsize%5D=100")" || {
        echo "  WARN: registry query failed; proceeding without HCP skip" >&2
        EXISTING_MODULES=""
        break
      }
    EXISTING_MODULES+="$(echo "$resp" | jq -r '.data[].attributes | "\(.name)/\(.provider)"')"$'\n'
    next="$(echo "$resp" | jq -r '.meta.pagination."next-page" // empty')"
    [ -z "$next" ] && break
    page="$next"
  done
else
  echo "WARN: TFE_TOKEN not set — skipping HCP registry check (GitHub-fork check only)." >&2
fi

module_in_registry() { # name provider
  printf '%s\n' "$EXISTING_MODULES" | grep -qxF "$1/$2"
}

branch_exists() { # owner/repo branch
  gh api "repos/$1/branches/$2" >/dev/null 2>&1
}

# Ensure the branch-based publish branch exists on a fork we own; if missing,
# create it from the fork's default branch (e.g. upstream ships only `master`,
# but we publish from `main`). terraform apply uses var.branch — keep
# PUBLISH_BRANCH aligned. Honors --dry-run (preview only).
ensure_publish_branch() { # owner/repo
  if branch_exists "$1" "$PUBLISH_BRANCH"; then
    echo "    branch '${PUBLISH_BRANCH}' present"
    return 0
  fi

  default="$(gh repo view "$1" --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo '')"
  if [ -z "$default" ]; then
    echo "    WARN: cannot determine default branch of ${1}; skipping branch fix" >&2
    BRANCH_WARNINGS=$((BRANCH_WARNINGS + 1))
    return 0
  fi

  if $DRY_RUN; then
    echo "    would create branch '${PUBLISH_BRANCH}' from '${default}' on ${1}"
    return 0
  fi

  sha="$(gh api "repos/$1/git/refs/heads/${default}" -q '.object.sha' 2>/dev/null || echo '')"
  if [ -z "$sha" ]; then
    echo "    WARN: could not resolve '${default}' SHA on ${1}; skipping branch fix" >&2
    BRANCH_WARNINGS=$((BRANCH_WARNINGS + 1))
    return 0
  fi

  if gh api -X POST "repos/$1/git/refs" \
      -f "ref=refs/heads/${PUBLISH_BRANCH}" -f "sha=${sha}" >/dev/null 2>&1; then
    echo "    created branch '${PUBLISH_BRANCH}' from '${default}' on ${1}"
  else
    echo "    WARN: failed to create branch '${PUBLISH_BRANCH}' on ${1}" >&2
    BRANCH_WARNINGS=$((BRANCH_WARNINGS + 1))
  fi
}

# --- Fork what's missing -----------------------------------------------------
BRANCH_WARNINGS=0
echo "Forking from ${SOURCE_ORG} into ${GITHUB_ORG} (skipping existing; publish branch '${PUBLISH_BRANCH}')..."
for repo in "${MODULES[@]}"; do
  name="${repo#terraform-aws-}" # terraform-aws-ec2-instance -> ec2-instance
  provider="aws"

  if module_in_registry "$name" "$provider"; then
    echo "  = ${name}/${provider} already in HCP registry, skipping"
    continue
  fi
  if gh repo view "${GITHUB_ORG}/${repo}" >/dev/null 2>&1; then
    echo "  = ${GITHUB_ORG}/${repo} fork already exists, skipping fork"
    ensure_publish_branch "${GITHUB_ORG}/${repo}"
    continue
  fi
  if $DRY_RUN; then
    echo "  + would fork ${SOURCE_ORG}/${repo} -> ${GITHUB_ORG}/${repo}"
    # Fork doesn't exist yet; preview against upstream so the master/main gap shows.
    if branch_exists "${SOURCE_ORG}/${repo}" "$PUBLISH_BRANCH"; then
      echo "    branch '${PUBLISH_BRANCH}' present upstream"
    else
      up_default="$(gh repo view "${SOURCE_ORG}/${repo}" --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo '?')"
      echo "    would create branch '${PUBLISH_BRANCH}' from '${up_default}' on the new fork"
    fi
    continue
  fi
  echo "  + forking ${SOURCE_ORG}/${repo}"
  gh repo fork "${SOURCE_ORG}/${repo}" --org "${GITHUB_ORG}" --clone=false --default-branch-only
  # Forking is async; wait briefly for the fork's refs to become available.
  for _ in 1 2 3 4 5; do gh repo view "${GITHUB_ORG}/${repo}" >/dev/null 2>&1 && break; sleep 2; done
  ensure_publish_branch "${GITHUB_ORG}/${repo}"
done

if [ "$BRANCH_WARNINGS" -gt 0 ]; then
  echo "WARNING: ${BRANCH_WARNINGS} repo(s) still missing the '${PUBLISH_BRANCH}' branch — resolve before terraform apply." >&2
fi

$DRY_RUN && { echo "Dry run complete — no changes made."; exit 0; }

echo "Done. Next: connect a VCS provider in HCP Terraform, then run terraform apply here."
echo "      terraform apply is idempotent — modules already published are left untouched."
