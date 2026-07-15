#!/usr/bin/env bash
# Idempotent HCP Terraform workspace destroy. Safe to call twice; a missing
# workspace counts as clean. Writes a machine-readable destroy result.
#
# Usage: teardown-sandbox.sh --org <org> --workspace <name> --result-out <file>
#        [--delete-workspace] [--timeout-mins 30]
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$LIB_DIR/common.sh"

ORG="" WORKSPACE="" RESULT_OUT="" DELETE_WS=false TIMEOUT_MINS=30
while [[ $# -gt 0 ]]; do
  case $1 in
    --org) ORG=$2; shift 2 ;;
    --workspace) WORKSPACE=$2; shift 2 ;;
    --result-out) RESULT_OUT=$2; shift 2 ;;
    --delete-workspace) DELETE_WS=true; shift ;;
    --timeout-mins) TIMEOUT_MINS=$2; shift 2 ;;
    *) die "teardown-sandbox.sh: unknown arg $1" ;;
  esac
done
[[ -n "$ORG" && -n "$WORKSPACE" ]] || die "teardown-sandbox.sh: --org and --workspace required"

emit() { # emit <status> <detail> <resource_count> <duration_s>
  local out
  out=$(jq -cn --arg ws "$WORKSPACE" --arg s "$1" --arg d "$2" \
    --argjson rc "${3:-null}" --argjson dur "${4:-null}" \
    '{workspace: $ws, status: $s, detail: $d, resource_count: $rc, duration_s: $dur}')
  [[ -n "$RESULT_OUT" ]] && printf '%s\n' "$out" > "$RESULT_OUT"
  printf '%s\n' "$out"
}

start_ts=$(date +%s)

# Only an HTTP 404 counts as "workspace not found = clean". Transport or auth
# failures MUST be reported as failed — treating them as clean orphans infra.
ws_json=$(tfe_api_with_code GET "/organizations/$ORG/workspaces/$WORKSPACE" || true)
case "${TFE_HTTP_CODE:-000}" in
  200) ws_id=$(jq -r '.data.id // empty' <<<"$ws_json" 2>/dev/null || true) ;;
  404)
    log "workspace $WORKSPACE not found (HTTP 404) — treating as clean"
    emit "clean" "workspace not found" 0 0
    exit 0 ;;
  *)
    emit "failed" "TFE API error looking up workspace (HTTP ${TFE_HTTP_CODE:-000})" null $(( $(date +%s) - start_ts ))
    exit 1 ;;
esac
if [[ -z "$ws_id" ]]; then
  emit "failed" "HTTP 200 but no workspace id in response" null $(( $(date +%s) - start_ts ))
  exit 1
fi

resource_count=$(jq -r '.data.attributes["resource-count"] // 0' <<<"$ws_json")
if [[ "$resource_count" == "0" ]]; then
  log "workspace $WORKSPACE already has 0 resources"
  if $DELETE_WS; then tfe_api DELETE "/organizations/$ORG/workspaces/$WORKSPACE" >/dev/null 2>&1 || true; fi
  emit "clean" "no resources" 0 $(( $(date +%s) - start_ts ))
  exit 0
fi

queue_destroy() {
  tfe_api POST "/runs" "$(jq -n --arg ws "$ws_id" '{
    data: {
      type: "runs",
      attributes: { "is-destroy": true, "auto-apply": true, message: "e2e-eval teardown" },
      relationships: { workspace: { data: { type: "workspaces", id: $ws } } }
    }
  }')"
}

log "queueing destroy run for $WORKSPACE ($resource_count resources)"
destroy_json=$(queue_destroy)
destroy_run=$(jq -r '.data.id // empty' <<<"$destroy_json" 2>/dev/null || true)
if [[ -z "$destroy_run" ]]; then
  warn "destroy queue failed, retrying once: $(jq -c '.errors // .' <<<"$destroy_json" 2>/dev/null | head -c 300)"
  sleep 10
  destroy_json=$(queue_destroy)
  destroy_run=$(jq -r '.data.id // empty' <<<"$destroy_json" 2>/dev/null || true)
fi
if [[ -z "$destroy_run" ]]; then
  emit "failed" "could not queue destroy run" "$resource_count" $(( $(date +%s) - start_ts ))
  exit 1
fi

deadline=$(( start_ts + TIMEOUT_MINS * 60 ))
status=""
while (( $(date +%s) < deadline )); do
  status=$(tfe_api GET "/runs/$destroy_run" 2>/dev/null | jq -r '.data.attributes.status // empty' || true)
  case "$status" in
    applied|planned_and_finished) break ;;
    errored|canceled|force_canceled|discarded)
      emit "failed" "destroy run $destroy_run ended: $status" "$resource_count" $(( $(date +%s) - start_ts ))
      exit 1 ;;
    *) sleep 15 ;;
  esac
done
if [[ "$status" != "applied" && "$status" != "planned_and_finished" ]]; then
  emit "timeout" "destroy run $destroy_run still $status after ${TIMEOUT_MINS}m" "$resource_count" $(( $(date +%s) - start_ts ))
  exit 1
fi

final_count=$(tfe_api GET "/organizations/$ORG/workspaces/$WORKSPACE" 2>/dev/null \
  | jq -r '.data.attributes["resource-count"] // 0' || echo "unknown")
if $DELETE_WS && [[ "$final_count" == "0" ]]; then
  tfe_api DELETE "/organizations/$ORG/workspaces/$WORKSPACE" >/dev/null 2>&1 || true
fi
if [[ "$final_count" == "0" ]]; then
  emit "clean" "destroy run $destroy_run applied" 0 $(( $(date +%s) - start_ts ))
else
  emit "dirty" "destroy applied but resource-count=$final_count" "$final_count" $(( $(date +%s) - start_ts ))
  exit 1
fi
