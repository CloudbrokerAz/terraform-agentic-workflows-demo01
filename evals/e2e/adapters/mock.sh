#!/usr/bin/env bash
# Runtime adapter: mock. Fabricates a plausible workflow run for $0 so the
# entire pipeline (runner → harvest → checks → judge-skip → report) can be
# exercised without an agent, GitHub, or HCP Terraform.
#
# Same contract as claude-code.sh. Honors MOCK_FAIL=1 (agent error) and
# MOCK_SLEEP_SECS (simulate wall time, useful for interrupt testing).
set -uo pipefail
ADAPTER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIB="$ADAPTER_DIR/../lib"
# shellcheck disable=SC1091
source "$LIB/common.sh"

[[ "${1:-}" == "run" ]] || die "usage: mock.sh run --prompt-file F --workdir D --out-dir O ..."
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
    *) die "mock.sh: unknown arg $1" ;;
  esac
done
[[ -f "$PROMPT_FILE" && -d "$WORKDIR" && -n "$OUT" ]] || die "mock.sh: missing required args"
mkdir -p "$OUT"

sleep "${MOCK_SLEEP_SECS:-0}"

# Fabricate the artifact tree a real workflow run would leave behind.
# Track is inferred from the prompt (consumer prompts carry an HCP block).
feature="mock-feature"
mkdir -p "$WORKDIR/specs/$feature/reports" "$WORKDIR/tests"
if grep -qi 'HCP Terraform Configuration' "$PROMPT_FILE"; then
  design="$WORKDIR/specs/$feature/consumer-design.md"
  report="$WORKDIR/specs/$feature/reports/deployment-report.md"
  {
    echo "# Deployment Report (mock)"
    echo "Run: run-MOCKMOCKMOCK1234"
    echo "Monthly cost estimate: \$12.34"
    echo "Overall: 8.2/10"
  } > "$report"
else
  design="$WORKDIR/specs/$feature/design.md"
  report="$WORKDIR/specs/$feature/reports/validation_$(date +%Y%m%d-%H%M%S).md"
  {
    echo "# Validation Report (mock)"
    echo "Overall: 8.4/10"
  } > "$report"
  cat > "$WORKDIR/tests/basic.tftest.hcl" <<'EOF'
run "noop" {
  command = plan
}
EOF
fi
{
  echo "# Design (mock)"
  echo "## Implementation Checklist"
  echo "- [x] item 1"
  echo "- [x] item 2"
} > "$design"
echo "# research (mock)" > "$WORKDIR/specs/$feature/research-mock.md"
cat > "$WORKDIR/main.tf" <<'EOF'
terraform {
  required_version = ">= 1.5.0"
}
EOF

# Fabricate a stamped transcript with Task phase events + a result event.
python3 - "$OUT/transcript.jsonl" <<'EOF'
import json, sys, time
out = open(sys.argv[1], "w")
now = time.time()
def emit(offset, event):
    out.write(json.dumps({"ts": now + offset, "event": event}) + "\n")
emit(0, {"type": "system", "subtype": "init", "session_id": "mock-session"})
t = 1
for i, agent in enumerate(["research", "design", "developer", "validator"]):
    emit(t, {"type": "assistant", "message": {"content": [{"type": "tool_use", "id": f"t{i}", "name": "Task", "input": {"subagent_type": f"tf-consumer-{agent}"}}]}})
    t += 5
    emit(t, {"type": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": f"t{i}"}]}})
    t += 1
emit(t, {"type": "result", "subtype": "success", "total_cost_usd": 0.0,
         "duration_ms": int(t * 1000), "num_turns": 42, "session_id": "mock-session",
         "result": "E2E test complete. Status: PASSED. See issue #1 for details."})
EOF

exit_code=0; status="passed"
if [[ "${MOCK_FAIL:-0}" == "1" ]]; then exit_code=1; status="error"; fi

jq -n \
  --argjson exit_code "$exit_code" \
  --arg status "$status" \
  --arg model "${MODEL:-mock}" \
  '{
    schema_version: 1, adapter: "mock", exit_code: $exit_code, status: $status,
    cost_usd: 0.0, duration_ms: 27000, wall_time_s: 27, num_turns: 42,
    session_id: "mock-session", model: $model, is_error: ($status != "passed"),
    result_text: "E2E test complete. Status: PASSED. See issue #1 for details."
  }' > "$OUT/agent-result.json"

log "mock adapter done: status=$status"
[[ "$status" == "passed" ]]
