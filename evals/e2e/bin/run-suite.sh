#!/usr/bin/env bash
# Suite entry point: select cases, run each via run-eval.sh with a parallel
# throttle, sweep straggler sandboxes, write suite.json, print a summary table,
# and regenerate the HTML report.
#
# Usage:
#   run-suite.sh [--cases <glob>] [--case <file>] [--tags a,b] [--track module|consumer]
#                [--parallel N] [--adapter mock|claude-code] [--dry-run]
#                [--keep-repos] [--skip-judge]
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EVAL_ROOT="${EVAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
export REPO_ROOT="${REPO_ROOT:-$(cd "$EVAL_ROOT/../.." && pwd)}"
# shellcheck disable=SC1091
source "$EVAL_ROOT/lib/common.sh"
# shellcheck disable=SC1091
source "$EVAL_ROOT/lib/case.sh"
load_env

CASES_GLOB="$EVAL_ROOT/cases/*/*.json"
SINGLE_CASE="" TAGS="" TRACK="" PARALLEL=1 ADAPTER="" DRY_RUN=false KEEP_REPOS=false SKIP_JUDGE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --cases) CASES_GLOB=$2; shift 2 ;;
    --case) SINGLE_CASE=$2; shift 2 ;;
    --tags) TAGS=$2; shift 2 ;;
    --track) TRACK=$2; shift 2 ;;
    --parallel) PARALLEL=$2; shift 2 ;;
    --adapter) ADAPTER=$2; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    --keep-repos) KEEP_REPOS=true; shift ;;
    --skip-judge) SKIP_JUDGE=true; shift ;;
    *) die "run-suite.sh: unknown arg $1" ;;
  esac
done

# ------------------------------------------------------------- selection ----
candidates=()
if [[ -n "$SINGLE_CASE" ]]; then
  candidates=("$SINGLE_CASE")
else
  shopt -s nullglob
  # shellcheck disable=SC2206
  candidates=($CASES_GLOB)
  shopt -u nullglob
fi
(( ${#candidates[@]} > 0 )) || die "no case files match: ${SINGLE_CASE:-$CASES_GLOB}"

selected=()
for f in "${candidates[@]}"; do
  [[ "$(basename "$f")" == _* ]] && continue   # _schema.json etc.
  jq -e . "$f" >/dev/null 2>&1 || die "invalid case JSON: $f"
  jq -e '(.id | type == "string") and (.track | type == "string")
         and (.prompt_file | type == "string") and (.timeout_minutes | type == "number")
         and (.judge.min_score | type == "number") and (.deterministic_checks | type == "array")
         and (.sandbox.deploy | type == "boolean")' "$f" >/dev/null 2>&1 \
    || die "case $f is missing required fields (see cases/_schema.json)"
  if [[ -n "$TRACK" && "$(jq -r '.track' "$f")" != "$TRACK" ]]; then continue; fi
  if [[ -n "$TAGS" ]]; then
    match=$(jq -r --arg tags "$TAGS" \
      '[.tags[]? as $t | ($tags | split(",")) | index($t)] | any(. != null)' "$f")
    [[ "$match" == "true" ]] || continue
  fi
  selected+=("$f")
done
(( ${#selected[@]} > 0 )) || die "no cases left after --tags/--track filters"

ids=$(for f in "${selected[@]}"; do jq -r '.id' "$f"; done | tr '\n' ' ')
log "selected ${#selected[@]} case(s): $ids"
if [[ "$DRY_RUN" == true ]]; then
  for f in "${selected[@]}"; do
    jq -r '"  " + .id + "  track=" + .track + "  deploy=" + (.sandbox.deploy | tostring) + "  timeout=" + (.timeout_minutes | tostring) + "m"' "$f"
  done
  exit 0
fi

# ------------------------------------------------------------- preflight ----
effective_adapter_for() { printf '%s' "${ADAPTER:-$(jq -r '.runtime.adapter' "$1")}"; }
any_deploy=false any_real=false
for f in "${selected[@]}"; do
  a=$(effective_adapter_for "$f")
  [[ "$a" != "mock" ]] && any_real=true
  if [[ "$a" != "mock" && "$(jq -r '.sandbox.deploy' "$f")" == "true" ]]; then any_deploy=true; fi
done

if [[ "$any_real" == true ]]; then
  if [[ -x "$REPO_ROOT/.foundations/scripts/bash/validate-env.sh" ]]; then
    # rc=2 means GATE checks passed but WARN-only tools are missing — proceed.
    "$REPO_ROOT/.foundations/scripts/bash/validate-env.sh" --json >/dev/null
    env_rc=$?
    if [[ $env_rc -ne 0 && $env_rc -ne 2 ]]; then
      die "environment validation failed (.foundations/scripts/bash/validate-env.sh, rc=$env_rc)"
    fi
    [[ $env_rc -eq 2 ]] && warn "env validation: WARN-only checks failed — continuing"
  fi
  command -v gh >/dev/null || die "gh CLI required for real runs"
  gh auth status >/dev/null 2>&1 || die "gh not authenticated"
  [[ -n "${EVAL_GITHUB_ACCOUNT:-}" && -n "${EVAL_TEMPLATE_REPO:-}" ]] \
    || die "EVAL_GITHUB_ACCOUNT and EVAL_TEMPLATE_REPO must be set (evals/e2e/.env)"
  # Throwaway-repo cleanup needs the delete_repo OAuth scope, which default
  # gh tokens lack. Without it every eval repo silently survives.
  if [[ "$KEEP_REPOS" != true ]] && ! gh auth status 2>&1 | grep -q 'delete_repo'; then
    die "gh token lacks the delete_repo scope — run: gh auth refresh -h github.com -s delete_repo (or pass --keep-repos and clean up manually)"
  fi
fi
if [[ "$any_deploy" == true ]]; then
  [[ -n "${TFE_TOKEN:-}" ]] || die "TFE_TOKEN required: selected cases deploy to HCP Terraform"
  tfe_api GET "/account/details" | jq -e '.data.id' >/dev/null \
    || die "TFE_TOKEN rejected by ${TFE_ADDR:-https://app.terraform.io}"
fi
if ! git -C "$REPO_ROOT" check-ignore -q "$EVAL_ROOT/results/probe" 2>/dev/null; then
  warn "evals/e2e/results/ is NOT git-ignored — add 'evals/e2e/results/' and 'evals/e2e/.env' to .gitignore"
fi

# ------------------------------------------------------------------ runs ----
RUN_ID=$(new_run_id)
RESULTS_DIR="$EVAL_ROOT/results/runs/$RUN_ID"
mkdir -p "$RESULTS_DIR"
log "run_id=$RUN_ID → $RESULTS_DIR (parallel=$PARALLEL)"

pids=()
# On INT/TERM: forward TERM to the children (their own traps run teardown),
# then fall through so the sweep and suite.json still happen.
SUITE_INTERRUPTED=false
on_suite_signal() {
  SUITE_INTERRUPTED=true
  warn "suite interrupted — terminating case runners (their teardowns will run)"
  local pid
  for pid in ${pids[@]+"${pids[@]}"}; do kill -TERM "$pid" 2>/dev/null; done
}
trap 'on_suite_signal' INT TERM

launch() {
  local f=$1 id
  id=$(jq -r '.id' "$f")
  local args=(--case "$f" --run-id "$RUN_ID" --results-dir "$RESULTS_DIR")
  [[ -n "$ADAPTER" ]] && args+=(--adapter "$ADAPTER")
  [[ "$KEEP_REPOS" == true ]] && args+=(--keep-repo)
  [[ "$SKIP_JUDGE" == true ]] && args+=(--skip-judge)
  "$SCRIPT_DIR/run-eval.sh" "${args[@]}" > "$RESULTS_DIR/$id.log" 2>&1 &
  pids+=($!)
  log "launched $id (pid $!)"
}

running() {
  local n=0 pid
  for pid in ${pids[@]+"${pids[@]}"}; do kill -0 "$pid" 2>/dev/null && n=$((n + 1)); done
  printf '%d' "$n"
}

for f in "${selected[@]}"; do
  [[ "$SUITE_INTERRUPTED" == true ]] && break
  while (( $(running) >= PARALLEL )); do sleep 2; done
  [[ "$SUITE_INTERRUPTED" == true ]] && break
  launch "$f"
done
# `wait` returns >128 when a trapped signal interrupts it — loop until all
# children are actually reaped so their teardowns have finished.
until wait; do :; done

# ----------------------------------------------------------------- sweep ----
if [[ "$any_deploy" == true ]]; then
  # Sweep every org the selected deploy cases target, not just EVAL_HCP_ORG.
  sweep_orgs=$(for f in "${selected[@]}"; do
    jq -r 'select(.sandbox.deploy) | .sandbox.hcp_org // empty' "$f"
  done; printf '%s\n' "${EVAL_HCP_ORG:-}")
  printf '%s\n' "$sweep_orgs" | sort -u | while IFS= read -r org; do
    [[ -n "$org" ]] || continue
    log "suite sweep: checking for straggler workspaces in $org"
    "$SCRIPT_DIR/sweep-sandboxes.sh" --org "$org" \
      --pattern "*$(suffix_from_run_id "$RUN_ID")*" || warn "sweep reported problems in $org"
  done
fi

# --------------------------------------------------------------- summary ----
RESULTS_FILE="$RESULTS_DIR/results.jsonl"
[[ -f "$RESULTS_FILE" ]] || die "no results were written — check $RESULTS_DIR/*.log"

jq -n \
  --arg run_id "$RUN_ID" \
  --arg git_sha "$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo unknown)" \
  --arg adapter "${ADAPTER:-per-case}" \
  --argjson parallel "$PARALLEL" \
  --slurpfile results "$RESULTS_FILE" \
  '{
    run_id: $run_id, git_sha: $git_sha, adapter: $adapter, parallel: $parallel,
    cases: ($results | length),
    passed: ([$results[] | select(.grade == "pass")] | length),
    total_cost_usd: ([$results[] | .agent.cost_usd // 0] | add),
    total_judge_cost_usd: ([$results[] | .judge.judge_cost_usd // 0] | add),
    total_wall_time_s: ([$results[] | .wall_time_s] | add)
  }' > "$RESULTS_DIR/suite.json"

echo ""
echo "┌─ E2E eval suite $RUN_ID ─"
jq -r '"│ " + (.case_id | . + (" " * ((28 - length)
       | if . < 1 then 1 else . end))) +
       (.grade | ascii_upcase | . + (" " * (6 - length))) +
       " judge=" + ((.judge.overall // "n/a") | tostring) +
       " cost=$" + ((.agent.cost_usd // 0) | tostring) +
       " wall=" + (.wall_time_s | tostring) + "s" +
       (if .sandbox.deployed then " destroy=" + (.sandbox.destroy_status // "?") else "" end)' \
  "$RESULTS_FILE"
jq -r '"└─ " + (.passed | tostring) + "/" + (.cases | tostring) + " passed, $" +
       ((.total_cost_usd // 0) | tostring) + " agent cost, " +
       ((.total_wall_time_s // 0) | tostring) + "s total"' "$RESULTS_DIR/suite.json"

# ---------------------------------------------------------------- report ----
python3 "$EVAL_ROOT/report/generate_report.py" \
  --results "$EVAL_ROOT/results" --out "$EVAL_ROOT/results/report.html" \
  && log "report → $EVAL_ROOT/results/report.html"

fails=$(jq -sr '[.[] | select(.grade != "pass")] | length' "$RESULTS_FILE")
[[ "$SUITE_INTERRUPTED" == true ]] && exit 130
exit $(( fails > 0 ))
