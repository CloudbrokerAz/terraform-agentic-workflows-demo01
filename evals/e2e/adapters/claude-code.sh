#!/usr/bin/env bash
# Runtime adapter: Claude Code headless. The ONLY file in the framework that
# invokes `claude`. Implements the adapter contract:
#
#   claude-code.sh run --prompt-file F --workdir D --out-dir O --timeout-secs N
#                      [--model M] [--max-turns K]
#
# Produces in O:
#   transcript.jsonl   — stream-json events stamped with arrival epoch
#   agent-result.json  — normalized result (schema below), even on timeout/crash
set -uo pipefail
ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$ADAPTER_DIR/../lib"
# shellcheck disable=SC1091
source "$LIB/common.sh"

[[ "${1:-}" == "run" ]] || die "usage: claude-code.sh run --prompt-file F --workdir D --out-dir O --timeout-secs N"
shift

PROMPT_FILE="" WORKDIR="" OUT="" TIMEOUT_SECS=3600 MODEL="" MAX_TURNS=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --prompt-file) PROMPT_FILE=$2; shift 2 ;;
    --workdir) WORKDIR=$2; shift 2 ;;
    --out-dir) OUT=$2; shift 2 ;;
    --timeout-secs) TIMEOUT_SECS=$2; shift 2 ;;
    --model) MODEL=$2; shift 2 ;;
    --max-turns) MAX_TURNS=$2; shift 2 ;;
    *) die "claude-code.sh: unknown arg $1" ;;
  esac
done
[[ -f "$PROMPT_FILE" && -d "$WORKDIR" && -n "$OUT" ]] || die "claude-code.sh: missing required args"
mkdir -p "$OUT"

command -v claude >/dev/null || die "claude CLI not found on PATH"

start_ts=$(date +%s)
args=(-p "$(cat "$PROMPT_FILE")" --output-format stream-json --verbose --dangerously-skip-permissions)
[[ -n "$MODEL" ]] && args+=(--model "$MODEL")
[[ -n "$MAX_TURNS" ]] && args+=(--max-turns "$MAX_TURNS")

# The pipeline runs in the background so a TERM/INT to this adapter can be
# forwarded (needed on macOS, where run-eval has no setsid group-kill; killing
# the stamp reader SIGPIPEs claude on its next write). claude's own exit code
# travels via a file since PIPESTATUS is lost across the background boundary.
rc_file="$OUT/.agent-rc"
rm -f "$rc_file"
set +e
(
  (
    cd "$WORKDIR" || { echo 97 > "$rc_file"; exit 97; }
    run_with_timeout "$TIMEOUT_SECS" claude "${args[@]}"
    echo $? > "$rc_file"
  ) | python3 "$LIB/stamp_lines.py" > "$OUT/transcript.jsonl"
) &
PIPE_PID=$!
trap 'kill -TERM "$PIPE_PID" 2>/dev/null' TERM INT
wait "$PIPE_PID"
wait "$PIPE_PID" 2>/dev/null   # re-wait if a trapped signal cut the first short
trap - TERM INT
exit_code=$(cat "$rc_file" 2>/dev/null || echo 143)
rm -f "$rc_file"
set -e
end_ts=$(date +%s)

status="passed"
if [[ $exit_code -eq 124 || $exit_code -eq 137 ]]; then
  status="timeout"   # GNU timeout TERM / KILL; watchdog fallback reports 143 (error)
elif [[ $exit_code -ne 0 ]]; then
  status="error"
fi

# The final stream-json event of type "result" carries cost/turn/session facts.
result_event=$(jq -c 'select(.event.type == "result") | .event' "$OUT/transcript.jsonl" 2>/dev/null | tail -1)
[[ -n "$result_event" ]] || result_event='{}'

# A zero exit code is not enough: the result event can carry is_error=true
# (e.g. max-turns hit), and a transcript without any result event means the
# stream was truncated (stamp failure / early death) — both are failures.
if [[ "$status" == "passed" ]]; then
  if [[ "$result_event" == '{}' ]]; then
    status="error"
    warn "claude exited 0 but no result event found in transcript — marking error"
  elif [[ "$(jq -r '.is_error // false' <<<"$result_event")" == "true" ]]; then
    status="error"
    warn "result event reports is_error=true — marking error"
  fi
fi

jq -n \
  --arg adapter "claude-code" \
  --argjson exit_code "$exit_code" \
  --arg status "$status" \
  --arg model "$MODEL" \
  --argjson wall "$(( end_ts - start_ts ))" \
  --argjson ev "$result_event" \
  '{
    schema_version: 1,
    adapter: $adapter,
    exit_code: $exit_code,
    status: $status,
    cost_usd: ($ev.total_cost_usd // null),
    duration_ms: ($ev.duration_ms // ($wall * 1000)),
    wall_time_s: $wall,
    num_turns: ($ev.num_turns // null),
    session_id: ($ev.session_id // null),
    model: (if $model == "" then ($ev.model // null) else $model end),
    is_error: ($ev.is_error // ($status != "passed")),
    result_text: ($ev.result // null)
  }' > "$OUT/agent-result.json"

log "claude-code adapter done: status=$status exit=$exit_code cost=$(jq -r '.cost_usd // "n/a"' "$OUT/agent-result.json")"
[[ "$status" == "passed" ]]
