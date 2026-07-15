#!/usr/bin/env bash
# Disaster-recovery sweep: destroy every HCP Terraform workspace in the org
# whose name matches a glob pattern. Used automatically at the end of a suite
# (scoped to the run suffix) and manually for orphan cleanup:
#
#   bin/sweep-sandboxes.sh --org hashi-demos-apj --pattern 'sandbox_consumer_*'
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EVAL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck disable=SC1091
source "$EVAL_ROOT/lib/common.sh"
load_env

ORG="${EVAL_HCP_ORG:-}" PATTERN="" DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case $1 in
    --org) ORG=$2; shift 2 ;;
    --pattern) PATTERN=$2; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) die "sweep-sandboxes.sh: unknown arg $1" ;;
  esac
done
[[ -n "$ORG" && -n "$PATTERN" ]] || die "usage: sweep-sandboxes.sh --org <org> --pattern '<glob>' [--dry-run]"

log "sweeping workspaces matching '$PATTERN' in org $ORG"
page=1 found=0 failed=0
while :; do
  resp=$(tfe_api GET "/organizations/$ORG/workspaces?page%5Bnumber%5D=$page&page%5Bsize%5D=100")
  jq -e '.data' <<<"$resp" >/dev/null 2>&1 \
    || die "TFE API error listing workspaces (bad token/org?): $(jq -c '.errors // .' <<<"$resp" 2>/dev/null | head -c 200)"
  names=$(jq -r '.data[].attributes.name' <<<"$resp")
  [[ -z "$names" ]] && break
  while IFS= read -r ws; do
    # shellcheck disable=SC2254
    case "$ws" in
      $PATTERN)
        found=$((found + 1))
        if $DRY_RUN; then
          log "would destroy: $ws"
        else
          "$EVAL_ROOT/lib/teardown-sandbox.sh" --org "$ORG" --workspace "$ws" --delete-workspace \
            || { warn "sweep failed for $ws"; failed=$((failed + 1)); }
        fi
        ;;
    esac
  done <<<"$names"
  next=$(jq -r '.meta.pagination["next-page"] // empty' <<<"$resp")
  [[ -z "$next" ]] && break
  page=$next
done

log "sweep complete: $found matched, $failed failed"
exit $(( failed > 0 ))
