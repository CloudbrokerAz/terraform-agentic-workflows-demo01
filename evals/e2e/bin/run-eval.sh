#!/usr/bin/env bash
# Single-case eval lifecycle:
#   parse case → arm teardown trap → provision throwaway repo → run adapter →
#   harvest → deterministic checks → judge → teardown → emit results.jsonl line
#
# Usage:
#   run-eval.sh --case <case.json> --run-id <id> --results-dir <dir>
#               [--adapter <name>] [--keep-repo] [--skip-judge]
#
# Teardown is trap-armed BEFORE provisioning and is idempotent: the sandbox
# workspace name is computed up front, so even a run killed at t=0 is swept.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export EVAL_ROOT="${EVAL_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
export REPO_ROOT="${REPO_ROOT:-$(cd "$EVAL_ROOT/../.." && pwd)}"
# shellcheck disable=SC1091
source "$EVAL_ROOT/lib/common.sh"
# shellcheck disable=SC1091
source "$EVAL_ROOT/lib/case.sh"
load_env

CASE_FILE="" RUN_ID="" RESULTS_DIR="" ADAPTER_OVERRIDE="" KEEP_REPO=false SKIP_JUDGE=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --case) CASE_FILE=$2; shift 2 ;;
    --run-id) RUN_ID=$2; shift 2 ;;
    --results-dir) RESULTS_DIR=$2; shift 2 ;;
    --adapter) ADAPTER_OVERRIDE=$2; shift 2 ;;
    --keep-repo) KEEP_REPO=true; shift ;;
    --skip-judge) SKIP_JUDGE=true; shift ;;
    *) die "run-eval.sh: unknown arg $1" ;;
  esac
done
[[ -f "$CASE_FILE" && -n "$RUN_ID" && -n "$RESULTS_DIR" ]] || die "run-eval.sh: --case, --run-id, --results-dir required"

CASE_ID=$(case_get "$CASE_FILE" '.id')
TRACK=$(case_get "$CASE_FILE" '.track')
ADAPTER=${ADAPTER_OVERRIDE:-$(case_get "$CASE_FILE" '.runtime.adapter')}
ADAPTER_BIN="$EVAL_ROOT/adapters/$ADAPTER.sh"

OUT="$RESULTS_DIR/$CASE_ID"
WORKDIR="$OUT/workdir"
mkdir -p "$OUT"

# Teardown state — initialized BEFORE the traps are armed so any die() from
# here on still runs teardown + writes a fallback result line.
WORKSPACE="" HCP_ORG="" DEPLOYS=false
REPO_FULL=""       # set after provisioning; teardown reads it
ISSUE_NUM="" PR_NUM=""
STARTED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
START_EPOCH=$(date +%s)

# ---------------------------------------------------------------- teardown ---
# Every selected case must leave a results.jsonl line, even when the script
# dies mid-provisioning — otherwise it silently vanishes from the report.
RESULT_WRITTEN=false
fallback_result_line() {
  jq -cn --arg run_id "$RUN_ID" --arg case_id "$CASE_ID" --arg track "$TRACK" \
    --arg started "$STARTED_AT" --arg ended "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg reason "$1" \
    --argjson wall $(( $(date +%s) - START_EPOCH )) --arg artifacts_dir "runs/$RUN_ID/$CASE_ID" \
    '{schema_version: 1, run_id: $run_id, case_id: $case_id, track: $track,
      status: "error", started_at: $started, ended_at: $ended, wall_time_s: $wall,
      phases: [], agent: null, sandbox: null, deterministic: null,
      validator_self_score: null, judge: null, judge_error: $reason,
      grade: "fail", repo: null, artifacts_dir: $artifacts_dir}'
}

TEARDOWN_DONE=false
teardown() {
  [[ "$TEARDOWN_DONE" == true ]] && return 0
  TEARDOWN_DONE=true
  if [[ "$DEPLOYS" == true && -n "$WORKSPACE" ]]; then
    log "teardown: destroying workspace $WORKSPACE"
    "$EVAL_ROOT/lib/teardown-sandbox.sh" \
      --org "$HCP_ORG" --workspace "$WORKSPACE" \
      --result-out "$OUT/destroy.json" --delete-workspace || \
      warn "SANDBOX DESTROY DID NOT COMPLETE CLEANLY for $WORKSPACE — run bin/sweep-sandboxes.sh"
  fi
  if [[ -n "$REPO_FULL" && "$KEEP_REPO" != true ]]; then
    log "teardown: deleting throwaway repo $REPO_FULL"
    delete_err=$(gh repo delete "$REPO_FULL" --yes 2>&1) || \
      warn "FAILED TO DELETE THROWAWAY REPO $REPO_FULL — delete it manually. gh said: $delete_err"
  fi
}
on_exit() {
  teardown
  if [[ "$RESULT_WRITTEN" != true ]]; then
    RESULT_WRITTEN=true
    warn "run ended before a result was assembled — writing fallback result line"
    append_jsonl "$RESULTS_DIR/results.jsonl" "$(fallback_result_line "run aborted before completion")" || true
  fi
}
# INT/TERM must EXIT — a non-exiting trap would resume the script with
# TEARDOWN_DONE=true and later deploys would never be destroyed. exit fires
# the EXIT trap, which handles teardown + the fallback result line.
trap 'on_exit' EXIT
trap 'exit 130' INT TERM

# Late validation — traps are armed, so these failures still record a result.
[[ -x "$ADAPTER_BIN" ]] || die "adapter not found/executable: $ADAPTER_BIN"

# Suffix comes from the run id ALONE (unique per run: timestamp + random);
# per-case uniqueness comes from workspace_pattern / CASE_ID in the repo name.
# This is also what makes the suite-level sweep pattern able to match.
SUFFIX=$(suffix_from_run_id "$RUN_ID")
WORKSPACE=$(workspace_name "$CASE_FILE" "$SUFFIX")
HCP_ORG=$(case_get "$CASE_FILE" '.sandbox.hcp_org')
if case_requires_deploy "$CASE_FILE" && [[ "$ADAPTER" != "mock" ]]; then DEPLOYS=true; fi

# ----------------------------------------------------------------- prompt ---
render_prompt "$CASE_FILE" "$SUFFIX" "$OUT/prompt.md"
log "case=$CASE_ID adapter=$ADAPTER suffix=$SUFFIX workspace=${WORKSPACE:-none}"

# -------------------------------------------------------------- provision ---
if [[ "$ADAPTER" == "mock" ]]; then
  mkdir -p "$WORKDIR"
  git -C "$WORKDIR" init -q -b main 2>/dev/null || true
  git -C "$WORKDIR" -c user.email=eval@local -c user.name=eval commit -q --allow-empty -m "eval seed" 2>/dev/null || true
else
  : "${EVAL_GITHUB_ACCOUNT:?set in evals/e2e/.env}" "${EVAL_TEMPLATE_REPO:?set in evals/e2e/.env}"
  REPO_NAME="tfaw-e2e-${CASE_ID}${SUFFIX//_/-}"
  REPO_FULL="$EVAL_GITHUB_ACCOUNT/$REPO_NAME"
  log "creating throwaway repo $REPO_FULL from $EVAL_TEMPLATE_REPO"
  retry 3 5 gh repo create "$REPO_FULL" --template "$EVAL_TEMPLATE_REPO" --private \
    || die "could not create throwaway repo $REPO_FULL"
  # Template generation is asynchronous: retry until the clone is non-empty
  # (a too-early clone can succeed but contain nothing).
  clone_ready() {
    rm -rf "$WORKDIR"
    gh repo clone "$REPO_FULL" "$WORKDIR" 2>/dev/null \
      && [[ -e "$WORKDIR/.claude" ]] \
      && git -C "$WORKDIR" rev-parse HEAD >/dev/null 2>&1
  }
  retry 5 5 clone_ready \
    || die "clone of $REPO_FULL never became ready (template generation incomplete?)"
fi

# ------------------------------------------------------------------- run ----
TIMEOUT_SECS=$(( $(case_get "$CASE_FILE" '.timeout_minutes') * 60 ))
MODEL=$(case_get "$CASE_FILE" '.runtime.model')
MAX_TURNS=$(case_get "$CASE_FILE" '.runtime.max_turns')
[[ -n "${EVAL_MODEL:-}" && -z "$MODEL" ]] && MODEL=$EVAL_MODEL

adapter_args=(run --prompt-file "$OUT/prompt.md" --workdir "$WORKDIR" --out-dir "$OUT" --timeout-secs "$TIMEOUT_SECS")
[[ -n "$MODEL" ]] && adapter_args+=(--model "$MODEL")
[[ -n "$MAX_TURNS" ]] && adapter_args+=(--max-turns "$MAX_TURNS")

# Run the adapter in the background so INT/TERM interrupt it immediately
# (a foreground child defers bash signal traps until it exits). setsid puts
# the adapter in its own process group so the kill reaches the timeout/claude
# grandchildren too — otherwise they keep running (and billing) headless.
INTERRUPTED=false
on_signal() {
  INTERRUPTED=true
  warn "interrupted — killing agent run, teardown will still execute"
  if [[ -n "${ADAPTER_PID:-}" ]]; then
    kill -TERM -- "-$ADAPTER_PID" 2>/dev/null || kill -TERM "$ADAPTER_PID" 2>/dev/null
  fi
}
trap 'on_signal' INT TERM

AGENT_RC=0
if command -v setsid >/dev/null; then
  setsid "$ADAPTER_BIN" "${adapter_args[@]}" &
else
  "$ADAPTER_BIN" "${adapter_args[@]}" &
fi
ADAPTER_PID=$!
wait "$ADAPTER_PID" || AGENT_RC=$?
wait "$ADAPTER_PID" 2>/dev/null   # reap if the first wait was cut short by a trap
trap 'exit 130' INT TERM          # back to exiting traps — see note at the initial arm

RUN_STATUS=$(jq -r '.status // "error"' "$OUT/agent-result.json" 2>/dev/null || echo error)
if [[ "$INTERRUPTED" == true ]]; then
  RUN_STATUS="error"
  SKIP_JUDGE=true
  [[ -f "$OUT/agent-result.json" ]] || jq -n '{schema_version: 1, adapter: "'"$ADAPTER"'",
    exit_code: 143, status: "error", cost_usd: null, duration_ms: null, num_turns: null,
    session_id: null, model: null, is_error: true, result_text: "interrupted"}' > "$OUT/agent-result.json"
  jq '.status = "error"' "$OUT/agent-result.json" > "$OUT/agent-result.json.tmp" \
    && mv "$OUT/agent-result.json.tmp" "$OUT/agent-result.json"
fi
log "agent run finished: status=$RUN_STATUS rc=$AGENT_RC interrupted=$INTERRUPTED"

# --------------------------------------------------------------- harvest ----
harvest_args=(--workdir "$WORKDIR" --out "$OUT")
[[ -n "$WORKSPACE" ]] && harvest_args+=(--workspace "$WORKSPACE" --org "$HCP_ORG")
"$EVAL_ROOT/lib/harvest.sh" "${harvest_args[@]}" || warn "harvest had errors"

# ---------------------------------------------------- GitHub facts (pre-rm) --
# Queried once here (before the repo is deleted) and fed to the checks layer,
# which no longer talks to gh itself.
ISSUE_COUNT="" PR_COUNT=""
if [[ -n "$REPO_FULL" ]]; then
  issues_json=$(gh issue list --repo "$REPO_FULL" --state all --json number 2>/dev/null || true)
  prs_json=$(gh pr list --repo "$REPO_FULL" --state all --json number 2>/dev/null || true)
  ISSUE_NUM=$(jq -r '.[0].number // empty' <<<"$issues_json" 2>/dev/null || true)
  PR_NUM=$(jq -r '.[0].number // empty' <<<"$prs_json" 2>/dev/null || true)
  ISSUE_COUNT=$(jq -r 'length' <<<"$issues_json" 2>/dev/null || true)
  PR_COUNT=$(jq -r 'length' <<<"$prs_json" 2>/dev/null || true)
fi

# ---------------------------------------------------------------- checks ----
check_args=(--case "$CASE_FILE" --workdir "$WORKDIR" --out "$OUT/checks.json")
[[ -n "$ISSUE_COUNT" ]] && check_args+=(--issue-count "$ISSUE_COUNT")
[[ -n "$PR_COUNT" ]] && check_args+=(--pr-count "$PR_COUNT")
"$EVAL_ROOT/checks/deterministic.sh" "${check_args[@]}" || warn "checks had errors"

# ----------------------------------------------------------------- judge ----
if [[ "$SKIP_JUDGE" == true ]] || { [[ "$ADAPTER" == "mock" ]] && [[ "${EVAL_JUDGE_MOCK:-0}" != "1" ]]; }; then
  log "judge skipped (adapter=$ADAPTER)"
  printf 'null\n' > "$OUT/judge-verdict.json"
  jq -n '{judge_error: null, skipped: true, cost_usd: null}' > "$OUT/judge-result.json"
else
  "$EVAL_ROOT/judge/run-judge.sh" --case "$CASE_FILE" --workdir "$WORKDIR" \
    --out-dir "$OUT" --run-status "$RUN_STATUS" || warn "judge had errors"
fi

# -------------------------------------------------------------- teardown ----
teardown   # explicit call so destroy facts land in checks before the result line
# (EXIT trap stays armed; teardown and the fallback line are both idempotent)

# Merge destroy outcome into checks.json and recompute the aggregate gate.
# (`.checks as $c` binding is required: inside `.required[] | ...` the context
# is the check-name string, so `.checks[.]` would error, not default.)
RECOMPUTE='.checks as $c
  | .pass = ([.required[] | $c[.] // {pass: false, skipped: false}] | all(.pass or .skipped))'
merge_failed() { # fail safe: without destroy evidence a deploy case must not pass
  warn "destroy-merge failed — forcing checks gate to fail"
  jq '.pass = false' "$OUT/checks.json" > "$OUT/checks.json.tmp" \
    && mv "$OUT/checks.json.tmp" "$OUT/checks.json"
}
if [[ -f "$OUT/destroy.json" ]]; then
  { jq --slurpfile d "$OUT/destroy.json" '
      .checks.destroy_clean = {pass: ($d[0].status == "clean"), skipped: false,
                               detail: $d[0].detail, duration_s: $d[0].duration_s}
      | '"$RECOMPUTE" "$OUT/checks.json" > "$OUT/checks.json.tmp" \
    && mv "$OUT/checks.json.tmp" "$OUT/checks.json"; } || merge_failed
elif [[ "$DEPLOYS" == true ]]; then
  { jq '.checks.destroy_clean = {pass: false, skipped: false, detail: "no destroy result recorded", duration_s: null}
      | '"$RECOMPUTE" "$OUT/checks.json" > "$OUT/checks.json.tmp" \
    && mv "$OUT/checks.json.tmp" "$OUT/checks.json"; } || merge_failed
elif jq -e '.required | index("destroy_clean")' "$OUT/checks.json" >/dev/null 2>&1; then
  # Case requires destroy_clean but this run never deployed (mock adapter):
  # record an explicit, visible skip instead of silently omitting the check.
  { jq '.checks.destroy_clean = {pass: false, skipped: true, detail: "no deploy this run (adapter='"$ADAPTER"')", duration_s: null}
      | '"$RECOMPUTE" "$OUT/checks.json" > "$OUT/checks.json.tmp" \
    && mv "$OUT/checks.json.tmp" "$OUT/checks.json"; } || merge_failed
fi

# ---------------------------------------------------------------- phases ----
python3 "$EVAL_ROOT/lib/parse_transcript.py" "$OUT/transcript.jsonl" \
  --specs-dir "$WORKDIR/specs" --run-start "$START_EPOCH" > "$OUT/phases.json" 2>/dev/null \
  || printf '{"phases": []}\n' > "$OUT/phases.json"

# ----------------------------------------------------------- result line ----
END_EPOCH=$(date +%s)
ENDED_AT=$(date -u +%Y-%m-%dT%H:%M:%SZ)
MIN_SCORE=$(case_get "$CASE_FILE" '.judge.min_score')
MIN_SCORE=${MIN_SCORE:-7.0}

# A missing intermediate file must degrade the line, never drop the case.
ensure_json() { [[ -s "$1" ]] && jq -e . "$1" >/dev/null 2>&1 || printf '%s\n' "$2" > "$1"; }
ensure_json "$OUT/agent-result.json" '{"adapter":null,"model":null,"cost_usd":null,"num_turns":null,"session_id":null,"exit_code":null,"status":"error"}'
ensure_json "$OUT/phases.json" '{"phases":[]}'
ensure_json "$OUT/checks.json" '{"required":[],"checks":{},"pass":false}'
ensure_json "$OUT/run-facts.json" '{"workspace":null,"run_id":null,"run_url":null,"apply_status":null,"cost_estimate_monthly_usd":null,"run_tasks":[],"validator_self_score":null}'
ensure_json "$OUT/judge-verdict.json" 'null'
ensure_json "$OUT/judge-result.json" '{"judge_error":"judge produced no result","skipped":false,"cost_usd":null}'

RESULT_LINE=$(jq -cn \
  --arg run_id "$RUN_ID" --arg case_id "$CASE_ID" --arg track "$TRACK" \
  --arg status "$RUN_STATUS" \
  --arg started "$STARTED_AT" --arg ended "$ENDED_AT" \
  --argjson wall $(( END_EPOCH - START_EPOCH )) \
  --slurpfile agent "$OUT/agent-result.json" \
  --slurpfile phases "$OUT/phases.json" \
  --slurpfile checks "$OUT/checks.json" \
  --slurpfile facts "$OUT/run-facts.json" \
  --slurpfile verdict "$OUT/judge-verdict.json" \
  --slurpfile jresult "$OUT/judge-result.json" \
  --argjson min "$MIN_SCORE" \
  --arg repo "$REPO_FULL" --arg issue "$ISSUE_NUM" --arg pr "$PR_NUM" \
  --arg kept "$KEEP_REPO" --arg deploys "$DEPLOYS" --arg adapter "$ADAPTER" \
  --arg artifacts_dir "runs/$RUN_ID/$CASE_ID" \
  '
  ($verdict[0]) as $j |
  ($j != null and ($j.overall // 0) >= $min and (($j.security_override_triggered // false) | not)) as $judge_ok |
  ($jresult[0].skipped // false) as $judge_skipped |
  {
    schema_version: 1,
    run_id: $run_id, case_id: $case_id, track: $track,
    status: $status,
    started_at: $started, ended_at: $ended, wall_time_s: $wall,
    phases: $phases[0].phases,
    agent: {
      adapter: $agent[0].adapter, model: $agent[0].model,
      cost_usd: $agent[0].cost_usd, num_turns: $agent[0].num_turns,
      session_id: $agent[0].session_id, exit_code: $agent[0].exit_code
    },
    sandbox: {
      deployed: ($deploys == "true"),
      workspace: $facts[0].workspace, run_id: $facts[0].run_id, run_url: $facts[0].run_url,
      apply_status: $facts[0].apply_status,
      cost_estimate_monthly_usd: $facts[0].cost_estimate_monthly_usd,
      run_tasks: $facts[0].run_tasks,
      destroy_status: ($checks[0].checks.destroy_clean // null | if . == null then null elif .pass then "clean" else .detail end)
    },
    deterministic: {pass: $checks[0].pass, checks: $checks[0].checks},
    validator_self_score: $facts[0].validator_self_score,
    judge: (if $j == null then null else {
      overall: $j.overall, production_ready: $j.production_ready,
      security_override: ($j.security_override_triggered // false),
      dimensions: ($j.dimensions | with_entries(.value = (.value | if type == "object" then .score else . end))),
      assertions_passed: ([$j.assertions[] | select(.pass)] | length),
      assertions_total: ($j.assertions | length),
      judge_cost_usd: $jresult[0].cost_usd
    } end),
    judge_error: $jresult[0].judge_error,
    grade: (if $status != "passed" then "fail"
            elif ($checks[0].pass | not) then "fail"
            elif $judge_skipped then (if $adapter == "mock" then "pass" else "fail" end)
            elif $judge_ok then "pass"
            else "fail" end),
    repo: {full_name: (if $repo == "" then null else $repo end),
           issue: (if $issue == "" then null else ($issue | tonumber) end),
           pr: (if $pr == "" then null else ($pr | tonumber) end),
           deleted: ($repo != "" and $kept != "true")},
    artifacts_dir: $artifacts_dir
  }')

if [[ -z "$RESULT_LINE" ]]; then
  warn "result-line jq failed — writing minimal fallback line"
  RESULT_LINE=$(fallback_result_line "result assembly failed")
fi
RESULT_WRITTEN=true
append_jsonl "$RESULTS_DIR/results.jsonl" "$RESULT_LINE"
GRADE=$(jq -r '.grade' <<<"$RESULT_LINE")
log "case $CASE_ID: status=$RUN_STATUS grade=$GRADE wall=$((END_EPOCH - START_EPOCH))s"
rm -rf "$WORKDIR"   # artifacts/ keeps the evidence; the clone is bulky
[[ "$GRADE" == "pass" ]]
