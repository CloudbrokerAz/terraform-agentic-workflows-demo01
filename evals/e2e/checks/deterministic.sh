#!/usr/bin/env bash
# Post-hoc deterministic gates. Re-runs tools in the workdir for trustworthy
# exit codes (no transcript parsing) and writes checks.json.
#
# Usage: deterministic.sh --case <case.json> --workdir <dir> --out <checks.json>
#                         [--issue-count N] [--pr-count N]  # pre-fetched by the runner
#
# The runner queries GitHub once (before the throwaway repo is deleted) and
# passes counts in — this script never talks to gh. destroy_clean is NOT
# evaluated here either; the runner merges it after teardown.
set -uo pipefail
CHECKS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$CHECKS_DIR/../lib/common.sh"

CASE_FILE="" WORKDIR="" OUT="" ISSUE_COUNT="" PR_COUNT=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --case) CASE_FILE=$2; shift 2 ;;
    --workdir) WORKDIR=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --issue-count) ISSUE_COUNT=$2; shift 2 ;;
    --pr-count) PR_COUNT=$2; shift 2 ;;
    *) die "deterministic.sh: unknown arg $1" ;;
  esac
done
[[ -f "$CASE_FILE" && -d "$WORKDIR" && -n "$OUT" ]] || die "deterministic.sh: --case, --workdir, --out required"

RESULTS='{}'
record() { # record <name> <pass|fail|skip> <detail>
  local name=$1 outcome=$2 detail=$3 dur=${4:-null}
  RESULTS=$(jq -c --arg n "$name" --arg o "$outcome" --arg d "$detail" --argjson t "$dur" \
    '. + {($n): {pass: ($o == "pass"), skipped: ($o == "skip"), detail: $d, duration_s: $t}}' <<<"$RESULTS")
  log "check $name: $outcome${detail:+ ($detail)}"
}

timed() { # timed <name> <cmd...> — record pass/fail from exit code, capture tail of output
  local name=$1; shift
  local t0 t1 out rc
  t0=$(date +%s)
  out=$( (cd "$WORKDIR" && "$@") 2>&1 ); rc=$?
  t1=$(date +%s)
  if [[ $rc -eq 0 ]]; then
    record "$name" pass "" $((t1 - t0))
  else
    record "$name" fail "$(tail -c 400 <<<"$out" | tr '\n' ' ' | tr -d '"')" $((t1 - t0))
  fi
  return $rc
}

wanted() { jq -e --arg c "$1" '.deterministic_checks | index($c)' "$CASE_FILE" >/dev/null; }
has_tool() { command -v "$1" >/dev/null; }

# --- artifacts: every expected glob must match >=1 file ---
if wanted artifacts; then
  missing=""
  while IFS= read -r pattern; do
    # shellcheck disable=SC2086
    if ! compgen -G "$WORKDIR/$pattern" >/dev/null; then
      missing="$missing $pattern"
    fi
  done < <(jq -r '.expected_artifacts[]' "$CASE_FILE")
  if [[ -z "$missing" ]]; then record artifacts pass ""; else record artifacts fail "missing:$missing"; fi
fi

# --- terraform gates ---
if wanted terraform_fmt; then
  if has_tool terraform; then timed terraform_fmt terraform fmt -check -recursive || true
  else record terraform_fmt skip "terraform not installed"; fi
fi

if wanted terraform_validate; then
  if has_tool terraform; then
    # `init -backend=false` skips the cloud{} backend; if init still trips on
    # the cloud block, validate a copy with it commented out.
    if (cd "$WORKDIR" && terraform init -backend=false -input=false >/dev/null 2>&1); then
      timed terraform_validate terraform validate -no-color || true
    else
      vcopy=$(mktemp -d)
      cp -R "$WORKDIR"/. "$vcopy/" 2>/dev/null
      # Comment out the ENTIRE cloud {} block (it is multiline — org/workspaces
      # etc.); brace-counting awk, written to a temp file (sed -i is not portable).
      for tf in "$vcopy"/*.tf; do
        [[ -f "$tf" ]] || continue
        awk '
          !inblock && /^[[:space:]]*cloud[[:space:]]*{/ { inblock = 1; depth = 0 }
          inblock {
            depth += gsub(/{/, "{") - gsub(/}/, "}")
            print "# " $0
            if (depth <= 0) inblock = 0
            next
          }
          { print }
        ' "$tf" > "$tf.tmp" && mv "$tf.tmp" "$tf"
      done
      if (cd "$vcopy" && terraform init -backend=false -input=false >/dev/null 2>&1 && terraform validate -no-color >/dev/null 2>&1); then
        record terraform_validate pass "validated with cloud block stubbed"
      else
        record terraform_validate fail "init/validate failed even with cloud block stubbed"
      fi
      rm -rf "$vcopy"
    fi
  else record terraform_validate skip "terraform not installed"; fi
fi

if wanted terraform_test; then
  if has_tool terraform; then
    # terraform test needs providers installed; init if validate didn't already
    [[ -d "$WORKDIR/.terraform" ]] \
      || (cd "$WORKDIR" && terraform init -backend=false -input=false >/dev/null 2>&1) || true
    timed terraform_test terraform test || true
  else record terraform_test skip "terraform not installed"; fi
fi

if wanted tflint; then
  if has_tool tflint; then timed tflint tflint --recursive || true
  else record tflint skip "tflint not installed"; fi
fi

if wanted trivy; then
  if has_tool trivy; then timed trivy trivy config . --severity CRITICAL,HIGH --exit-code 1 --quiet || true
  else record trivy skip "trivy not installed"; fi
fi

# --- GitHub evidence (counts pre-fetched by the runner before repo deletion) ---
if wanted issue_created; then
  if [[ -n "$ISSUE_COUNT" ]]; then
    if [[ "$ISSUE_COUNT" -gt 0 ]]; then record issue_created pass "issues=$ISSUE_COUNT"; else record issue_created fail "no issues found"; fi
  else record issue_created skip "no repo evidence provided"; fi
fi

if wanted pr_created; then
  if [[ -n "$PR_COUNT" ]]; then
    if [[ "$PR_COUNT" -gt 0 ]]; then record pr_created pass "prs=$PR_COUNT"; else record pr_created fail "no PRs found"; fi
  else record pr_created skip "no repo evidence provided"; fi
fi

# --- checklist completion: no unchecked items left in the design doc ---
if wanted checklist_complete; then
  design=$(find "$WORKDIR"/specs -maxdepth 2 -name '*design*.md' 2>/dev/null | head -1)
  if [[ -z "$design" ]]; then
    record checklist_complete fail "no design doc found"
  elif grep -qE '^[[:space:]]*[-*] \[ \]' "$design"; then
    record checklist_complete fail "unchecked items remain in $(basename "$design")"
  else
    record checklist_complete pass ""
  fi
fi

# Aggregate: pass ⇔ every REQUIRED check passed (skips don't fail the gate but
# are visible). destroy_clean is excluded here — the runner merges it after
# teardown and recomputes .pass.
required=$(jq -c '.deterministic_checks' "$CASE_FILE")
jq -n --argjson checks "$RESULTS" --argjson required "$required" '{
  required: $required,
  checks: $checks,
  pass: ([$required[] | select(. != "destroy_clean") | $checks[.] // {pass: false, skipped: false}]
         | all(.pass or .skipped))
}' > "$OUT"
log "deterministic checks → $OUT (pass=$(jq -r '.pass' "$OUT"))"
