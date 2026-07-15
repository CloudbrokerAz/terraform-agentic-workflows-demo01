#!/usr/bin/env bash
# Launch the independent judge in a FRESH headless session (zero shared context
# with the graded run), extract and validate its JSON verdict.
#
# Usage: run-judge.sh --case <case.json> --workdir <dir> --out-dir <dir>
#                     [--run-status passed|failed|timeout|error]
#
# Writes: <out-dir>/judge-verdict.json  (null + judge_error flag on failure)
#         <out-dir>/judge-result.json   (judge session cost/duration facts)
set -uo pipefail
JUDGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$JUDGE_DIR/../lib/common.sh"

CASE_FILE="" WORKDIR="" OUT="" RUN_STATUS="passed"
while [[ $# -gt 0 ]]; do
  case $1 in
    --case) CASE_FILE=$2; shift 2 ;;
    --workdir) WORKDIR=$2; shift 2 ;;
    --out-dir) OUT=$2; shift 2 ;;
    --run-status) RUN_STATUS=$2; shift 2 ;;
    *) die "run-judge.sh: unknown arg $1" ;;
  esac
done
[[ -f "$CASE_FILE" && -d "$WORKDIR" && -n "$OUT" ]] || die "run-judge.sh: --case, --workdir, --out-dir required"
mkdir -p "$OUT"

fail_soft() {
  warn "judge failed: $1"
  printf 'null\n' > "$OUT/judge-verdict.json"
  jq -n --arg err "$1" '{judge_error: $err, cost_usd: null}' > "$OUT/judge-result.json"
  exit 0   # a broken judge never fails the pipeline; the result records judge_error
}

command -v claude >/dev/null || fail_soft "claude CLI not found"

case_id=$(jq -r '.id' "$CASE_FILE")
rubric=$(jq -r '.judge.rubric' "$CASE_FILE")
min_score=$(jq -r '.judge.min_score' "$CASE_FILE")
assertions=$(jq -r '.judge.assertions[] | "- " + .' "$CASE_FILE")
track=$(jq -r '.track' "$CASE_FILE")
tests_hint=""
[[ "$track" == "module" ]] && tests_hint=", tests under \`tests/\`"
run_incomplete=false
[[ "$RUN_STATUS" == "timeout" || "$RUN_STATUS" == "error" ]] && run_incomplete=true

render() {
  sed -e "s|{{CASE_ID}}|$case_id|g" \
      -e "s|{{RUBRIC}}|$rubric|g" \
      -e "s|{{TESTS_HINT}}|$tests_hint|g" \
      -e "s|{{DIFF_PATH}}|$OUT/artifacts/git-diff.patch|g" \
      -e "s|{{CHECKS_PATH}}|$OUT/checks.json|g" \
      -e "s|{{FACTS_PATH}}|$OUT/run-facts.json|g" \
      -e "s|{{RUN_STATUS}}|$RUN_STATUS|g" \
      -e "s|{{RUN_INCOMPLETE}}|$run_incomplete|g" \
      "$JUDGE_DIR/judge-prompt-template.md" \
  | awk -v a="$assertions" '{ if ($0 == "{{ASSERTIONS}}") print a; else print }'
}
render > "$OUT/judge-prompt.md"

invoke_judge() {
  (
    cd "$WORKDIR" || exit 97
    run_with_timeout 1800 claude -p "$(cat "$OUT/judge-prompt.md")${1:-}" \
      --output-format json \
      --allowedTools "Skill,Read,Glob,Grep,Bash(git diff:*),Bash(git log:*),Bash(terraform providers:*)" \
      ${JUDGE_MODEL:+--model "$JUDGE_MODEL"}
  )
}

extract_verdict() { # stdin: claude json envelope → verdict json on stdout, rc!=0 if invalid
  local envelope verdict
  envelope=$(cat)
  verdict=$(jq -r '.result // empty' <<<"$envelope" 2>/dev/null \
    | sed -n '/^```/,/^```/p' | sed '1d;$d')
  # Tolerate a bare (unfenced) JSON final message too.
  if [[ -z "$verdict" ]]; then
    verdict=$(jq -r '.result // empty' <<<"$envelope" 2>/dev/null)
  fi
  jq -e '.overall != null and .dimensions != null and (.assertions | type == "array")' <<<"$verdict" >/dev/null 2>&1 || return 1
  printf '%s' "$verdict"
}

log "judging $case_id (rubric=$rubric, status=$RUN_STATUS)"
envelope=$(invoke_judge) || true
printf '%s' "$envelope" > "$OUT/judge-envelope.json"
verdict=$(extract_verdict <<<"$envelope") || {
  warn "verdict parse failed — retrying once with a JSON-only nudge"
  envelope=$(invoke_judge $'\n\nIMPORTANT: your previous output was not valid JSON. Respond with ONLY the fenced ```json verdict block.') || true
  printf '%s' "$envelope" > "$OUT/judge-envelope.json"
  verdict=$(extract_verdict <<<"$envelope") || fail_soft "verdict invalid after retry"
}

printf '%s\n' "$verdict" > "$OUT/judge-verdict.json"
jq -n \
  --argjson cost "$(jq '.total_cost_usd // null' <<<"$envelope")" \
  --argjson dur "$(jq '.duration_ms // null' <<<"$envelope")" \
  --arg min "$min_score" \
  '{judge_error: null, cost_usd: $cost, duration_ms: $dur, min_score: ($min | tonumber)}' \
  > "$OUT/judge-result.json"
log "judge verdict: overall=$(jq -r '.overall' "$OUT/judge-verdict.json") (min=$min_score)"
