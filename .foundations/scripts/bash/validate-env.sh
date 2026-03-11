#!/usr/bin/env bash

# Environment validation script with GATE/WARN severity classification
#
# Each check is classified as:
#   GATE — Failure blocks all progress. Orchestrators MUST NOT proceed.
#   WARN — Failure degrades capability but does not block progress.
#
# Usage: ./validate-env.sh [OPTIONS]
#
# OPTIONS:
#   --json              Output in JSON format (includes gate_passed boolean)
#   --help, -h          Show help message
#
# EXIT CODES:
#   0: All checks passed (GATE and WARN)
#   1: One or more GATE checks failed — orchestrators MUST stop
#   2: All GATE checks passed but one or more WARN checks failed

set -euo pipefail

# Parse command line arguments
JSON_MODE=false

for arg in "$@"; do
    case "$arg" in
        --json)
            JSON_MODE=true
            ;;
        --help|-h)
            cat << 'EOF'
Usage: validate-env.sh [OPTIONS]

Validate environment prerequisites for Terraform module operations.

Each check has a severity:
  GATE  Failure blocks all progress. Orchestrators MUST stop.
  WARN  Failure degrades capability. Orchestrators may proceed.

GATE CHECKS:
  TFE_TOKEN          Terraform Cloud/Enterprise API token
  GITHUB_TOKEN       GitHub Personal Access Token (github.com)
  GH_CLI             GitHub CLI installed and authenticated
                     (Required: issue creation is mandatory audit trail)
  TERRAFORM          Terraform CLI installed (>= 1.5)

WARN CHECKS:
  TFLINT             TFLint installed (code quality, non-blocking)
  PRE_COMMIT         pre-commit installed (hooks, non-blocking)
  TRIVY              Trivy installed (security scanning, non-blocking)
  TERRAFORM_DOCS     terraform-docs installed (doc generation, non-blocking)

OPTIONS:
  --json              Output in JSON format (includes gate_passed, checks array)
  --help, -h          Show this help message

EXIT CODES:
  0: All checks passed
  1: One or more GATE checks failed — MUST stop
  2: GATE checks passed, one or more WARN checks failed

JSON OUTPUT SCHEMA:
  {
    "gate_passed": true|false,
    "checks": [
      {"name": "TFE_TOKEN", "severity": "GATE", "passed": true|false, "detail": "..."},
      ...
    ]
  }

EOF
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option '$arg'. Use --help for usage information." >&2
            exit 1
            ;;
    esac
done

# --- Check definitions ---
# Each check: name, severity, passed, detail
declare -a check_names=()
declare -a check_severities=()
declare -a check_passed=()
declare -a check_details=()

add_check() {
    local name="$1" severity="$2" passed="$3" detail="$4"
    check_names+=("$name")
    check_severities+=("$severity")
    check_passed+=("$passed")
    check_details+=("$detail")
}

# GATE: TFE_TOKEN
if [[ -z "${TFE_TOKEN:-}" ]]; then
    add_check "TFE_TOKEN" "GATE" "false" "NOT SET — export TFE_TOKEN from https://app.terraform.io/app/settings/tokens"
else
    add_check "TFE_TOKEN" "GATE" "true" "SET"
fi

# GATE: GITHUB_TOKEN
if [[ -n "${GITHUB_TOKEN:-}" ]]; then
    add_check "GITHUB_TOKEN" "GATE" "true" "SET"
else
    add_check "GITHUB_TOKEN" "GATE" "false" "NOT SET — export GITHUB_TOKEN"
fi

# GATE: GH_CLI (required for issue creation — audit trail)
if ! command -v gh &> /dev/null; then
    add_check "GH_CLI" "GATE" "false" "NOT INSTALLED — see: https://cli.github.com"
elif gh auth status --hostname github.com &> /dev/null; then
    add_check "GH_CLI" "GATE" "true" "AUTHENTICATED (github.com)"
elif [[ -n "${GITHUB_TOKEN:-}" ]]; then
    add_check "GH_CLI" "GATE" "true" "AUTHENTICATED via GITHUB_TOKEN (github.com)"
else
    add_check "GH_CLI" "GATE" "false" "NOT AUTHENTICATED — export GITHUB_TOKEN"
fi

# GATE: Terraform CLI (>= 1.5)
if ! command -v terraform &> /dev/null; then
    add_check "TERRAFORM" "GATE" "false" "NOT INSTALLED — see: https://developer.hashicorp.com/terraform/install"
else
    # Parse version from JSON first (space-tolerant), fallback to text output.
    # NOTE: avoid `head -1` in pipelines — with pipefail, SIGPIPE causes false
    # failures and the || fallback concatenates stdout from multiple commands.
    TF_VERSION=$(terraform version -json 2>/dev/null | grep -oE '"terraform_version"\s*:\s*"[^"]+"' | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || true)
    if [[ -z "$TF_VERSION" ]]; then
        TF_VERSION=$(terraform version 2>/dev/null | grep -oE -m1 '[0-9]+\.[0-9]+\.[0-9]+' || echo "0.0.0")
    fi
    TF_MAJOR=$(echo "$TF_VERSION" | cut -d. -f1)
    TF_MINOR=$(echo "$TF_VERSION" | cut -d. -f2)
    if [[ "$TF_MAJOR" -gt 1 ]] || { [[ "$TF_MAJOR" -eq 1 ]] && [[ "$TF_MINOR" -ge 14 ]]; }; then
        add_check "TERRAFORM" "GATE" "true" "INSTALLED (v${TF_VERSION})"
    else
        add_check "TERRAFORM" "GATE" "false" "VERSION TOO OLD (v${TF_VERSION}) — requires >= 1.14. See: https://developer.hashicorp.com/terraform/install"
    fi
fi

# WARN: TFLint
# NOTE: version extraction uses bash regex instead of piped grep to avoid
# SIGPIPE under pipefail (see Terraform check comment above for rationale).
if command -v tflint &> /dev/null; then
    TFLINT_RAW=$(tflint --version 2>/dev/null || true)
    if [[ "$TFLINT_RAW" =~ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        TFLINT_VERSION="${BASH_REMATCH[1]}"
    else
        TFLINT_VERSION="unknown"
    fi
    add_check "TFLINT" "WARN" "true" "INSTALLED (v${TFLINT_VERSION})"
else
    add_check "TFLINT" "WARN" "false" "NOT INSTALLED — code quality linting unavailable"
fi

# WARN: pre-commit
if command -v pre-commit &> /dev/null; then
    PRE_COMMIT_RAW=$(pre-commit --version 2>/dev/null || true)
    if [[ "$PRE_COMMIT_RAW" =~ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        PRE_COMMIT_VERSION="${BASH_REMATCH[1]}"
    else
        PRE_COMMIT_VERSION="unknown"
    fi
    add_check "PRE_COMMIT" "WARN" "true" "INSTALLED (v${PRE_COMMIT_VERSION})"
else
    add_check "PRE_COMMIT" "WARN" "false" "NOT INSTALLED — git hooks unavailable"
fi

# WARN: Trivy
if command -v trivy &> /dev/null; then
    TRIVY_RAW=$(trivy --version 2>/dev/null || true)
    if [[ "$TRIVY_RAW" =~ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        TRIVY_VERSION="${BASH_REMATCH[1]}"
    else
        TRIVY_VERSION="unknown"
    fi
    add_check "TRIVY" "WARN" "true" "INSTALLED (v${TRIVY_VERSION})"
else
    add_check "TRIVY" "WARN" "false" "NOT INSTALLED — security scanning unavailable. See: https://aquasecurity.github.io/trivy"
fi

# WARN: terraform-docs
if command -v terraform-docs &> /dev/null; then
    TFDOCS_RAW=$(terraform-docs --version 2>/dev/null || true)
    if [[ "$TFDOCS_RAW" =~ ([0-9]+\.[0-9]+\.[0-9]+) ]]; then
        TFDOCS_VERSION="${BASH_REMATCH[1]}"
    else
        TFDOCS_VERSION="unknown"
    fi
    add_check "TERRAFORM_DOCS" "WARN" "true" "INSTALLED (v${TFDOCS_VERSION})"
else
    add_check "TERRAFORM_DOCS" "WARN" "false" "NOT INSTALLED — documentation generation unavailable. See: https://terraform-docs.io"
fi

# --- Evaluate results ---
gate_failed=0
warn_failed=0
for i in "${!check_names[@]}"; do
    if [[ "${check_passed[$i]}" == "false" ]]; then
        if [[ "${check_severities[$i]}" == "GATE" ]]; then
            gate_failed=$((gate_failed + 1))
        else
            warn_failed=$((warn_failed + 1))
        fi
    fi
done

gate_passed="true"
[[ $gate_failed -gt 0 ]] && gate_passed="false"

if [[ $gate_failed -gt 0 ]]; then
    EXIT_CODE=1
elif [[ $warn_failed -gt 0 ]]; then
    EXIT_CODE=2
else
    EXIT_CODE=0
fi

# --- Output ---
if $JSON_MODE; then
    # Build checks JSON array
    checks_json=""
    for i in "${!check_names[@]}"; do
        [[ -n "$checks_json" ]] && checks_json+=","
        checks_json+=$(printf '{"name":"%s","severity":"%s","passed":%s,"detail":"%s"}' \
            "${check_names[$i]}" "${check_severities[$i]}" "${check_passed[$i]}" "${check_details[$i]}")
    done

    printf '{"gate_passed":%s,"checks":[%s]}\n' "$gate_passed" "$checks_json"
else
    echo "Environment Validation"
    echo "======================"
    echo ""

    for i in "${!check_names[@]}"; do
        local_severity="${check_severities[$i]}"
        local_name="${check_names[$i]}"
        local_status="Passed"
        [[ "${check_passed[$i]}" == "false" ]] && local_status="FAILED"
        echo "  [$local_severity] $local_name — $local_status — ${check_details[$i]}"
    done

    echo ""
    echo "Summary"
    echo "-------"
    if [[ $gate_failed -gt 0 ]]; then
        echo "BLOCKED: $gate_failed GATE check(s) failed. Cannot proceed."
        echo ""
        echo "Quick Setup:"
        step=1
        for i in "${!check_names[@]}"; do
            if [[ "${check_passed[$i]}" == "false" && "${check_severities[$i]}" == "GATE" ]]; then
                echo "  $step. ${check_names[$i]}: ${check_details[$i]}"
                step=$((step + 1))
            fi
        done
        echo ""
        echo "For permanent setup, add exports to your ~/.bashrc or ~/.zshrc"
    elif [[ $warn_failed -gt 0 ]]; then
        echo "PASSED (with warnings): All GATE checks passed. $warn_failed WARN check(s) failed."
    else
        echo "ALL PASSED: Environment is fully configured."
    fi
fi

# Initialize tools (idempotent — always run when gates pass)
if [[ $EXIT_CODE -ne 1 ]]; then
    if ! $JSON_MODE; then
        echo ""
        echo "Tool Initialization"
        echo "==================="
        echo ""
    fi

    if command -v tflint &> /dev/null; then
        if ! $JSON_MODE; then echo "Initializing TFLint..."; fi
        if ! tflint --init >/dev/null 2>&1; then
            if ! $JSON_MODE; then echo "WARNING: TFLint init failed, continuing..."; fi
        fi
        if ! $JSON_MODE; then echo ""; fi
    fi

    if command -v pre-commit &> /dev/null; then
        if ! $JSON_MODE; then echo "Installing pre-commit hooks..."; fi
        pre-commit install >/dev/null 2>&1 || true
        if ! $JSON_MODE; then echo ""; fi
    fi
fi

exit $EXIT_CODE
