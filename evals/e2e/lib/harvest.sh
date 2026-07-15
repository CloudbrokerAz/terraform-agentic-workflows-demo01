#!/usr/bin/env bash
# Harvest artifacts and facts from a finished (or killed) workflow run.
# Always safe to call — every step tolerates missing inputs.
#
# Usage: harvest.sh --workdir <dir> --out <case_out_dir> [--workspace <tfe_ws_name>] [--org <tfe_org>]
set -uo pipefail
LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$LIB_DIR/common.sh"

WORKDIR="" OUT="" WORKSPACE="" ORG=""
while [[ $# -gt 0 ]]; do
  case $1 in
    --workdir) WORKDIR=$2; shift 2 ;;
    --out) OUT=$2; shift 2 ;;
    --workspace) WORKSPACE=$2; shift 2 ;;
    --org) ORG=$2; shift 2 ;;
    *) die "harvest.sh: unknown arg $1" ;;
  esac
done
[[ -d "$WORKDIR" && -n "$OUT" ]] || die "harvest.sh: --workdir and --out required"
mkdir -p "$OUT/artifacts"

# 1. specs/ artifacts
if [[ -d "$WORKDIR/specs" ]]; then
  cp -R "$WORKDIR/specs" "$OUT/artifacts/specs"
fi

# 2. git evidence (workflow runs on a feature branch off main)
if git -C "$WORKDIR" rev-parse --git-dir >/dev/null 2>&1; then
  git -C "$WORKDIR" log --oneline -50 > "$OUT/artifacts/git-log.txt" 2>/dev/null || true
  local_base=$(git -C "$WORKDIR" rev-parse --verify origin/main 2>/dev/null \
    || git -C "$WORKDIR" rev-parse --verify main 2>/dev/null || true)
  if [[ -n "$local_base" ]]; then
    git -C "$WORKDIR" diff "$local_base"...HEAD > "$OUT/artifacts/git-diff.patch" 2>/dev/null || true
  fi
fi

# 3. Terraform code snapshot (root-level; workflows write TF at repo root).
# Copy workdir-relative paths — `cp --parents` is GNU-only and replicated the
# absolute path into the snapshot.
mkdir -p "$OUT/artifacts/tf-files"
(
  cd "$WORKDIR" || exit 0
  find . -maxdepth 2 -name '*.tf' -not -path '*/.terraform/*' 2>/dev/null \
  | while IFS= read -r f; do
      mkdir -p "$OUT/artifacts/tf-files/$(dirname "$f")"
      cp "$f" "$OUT/artifacts/tf-files/$f" 2>/dev/null || true
    done
)

# 4. Validator self-score (signal only; never shown to the judge)
self_score=$(grep -rhoE 'Overall[^0-9]*([0-9]+(\.[0-9]+)?)\s*/\s*10' \
    "$WORKDIR"/specs/*/reports/ 2>/dev/null \
  | grep -oE '[0-9]+(\.[0-9]+)?' | head -1 || true)

# 5. Sandbox run facts: run id from the deployment report, enriched via TFE API.
run_id=$(grep -rhoE 'run-[A-Za-z0-9]{16}' "$WORKDIR"/specs/*/reports/ 2>/dev/null | head -1 || true)
run_url="" apply_status="" cost_monthly="" task_stages="[]"
if [[ -z "$run_id" && -n "$WORKSPACE" && -n "$ORG" && -n "${TFE_TOKEN:-}" ]]; then
  ws_json=$(tfe_api GET "/organizations/$ORG/workspaces/$WORKSPACE" 2>/dev/null || true)
  ws_id=$(jq -r '.data.id // empty' <<<"$ws_json" 2>/dev/null || true)
  if [[ -n "$ws_id" ]]; then
    run_id=$(tfe_api GET "/workspaces/$ws_id/runs?page%5Bsize%5D=1" 2>/dev/null \
      | jq -r '.data[0].id // empty' 2>/dev/null || true)
  fi
fi
if [[ -n "$run_id" && -n "${TFE_TOKEN:-}" ]]; then
  run_json=$(tfe_api GET "/runs/$run_id" 2>/dev/null || true)
  apply_status=$(jq -r '.data.attributes.status // empty' <<<"$run_json" 2>/dev/null || true)
  ce_id=$(jq -r '.data.relationships["cost-estimate"].data.id // empty' <<<"$run_json" 2>/dev/null || true)
  if [[ -n "$ce_id" ]]; then
    cost_monthly=$(tfe_api GET "/cost-estimates/$ce_id" 2>/dev/null \
      | jq -r '.data.attributes["proposed-monthly-cost"] // empty' 2>/dev/null || true)
  fi
  task_stages=$(tfe_api GET "/runs/$run_id/task-stages" 2>/dev/null \
    | jq -c '[.data[]?.attributes | {stage, status}]' 2>/dev/null || echo '[]')
fi
if [[ -z "$run_url" && -n "$run_id" && -n "$ORG" && -n "$WORKSPACE" ]]; then
  run_url="${TFE_ADDR:-https://app.terraform.io}/app/$ORG/workspaces/$WORKSPACE/runs/$run_id"
fi
# Fallback cost estimate: parse the deployment report's cost line.
if [[ -z "$cost_monthly" ]]; then
  cost_monthly=$(grep -rhoiE '(monthly cost|cost estimate)[^0-9$]*\$?([0-9]+(\.[0-9]+)?)' \
      "$WORKDIR"/specs/*/reports/ 2>/dev/null \
    | grep -oE '[0-9]+(\.[0-9]+)?' | head -1 || true)
fi

jq -n \
  --arg workspace "$WORKSPACE" \
  --arg run_id "$run_id" \
  --arg run_url "$run_url" \
  --arg apply_status "$apply_status" \
  --arg cost "$cost_monthly" \
  --arg self "$self_score" \
  --argjson task_stages "$task_stages" \
  '{
    workspace: (if $workspace == "" then null else $workspace end),
    run_id: (if $run_id == "" then null else $run_id end),
    run_url: (if $run_url == "" then null else $run_url end),
    apply_status: (if $apply_status == "" then null else $apply_status end),
    cost_estimate_monthly_usd: (if $cost == "" then null else ($cost | tonumber) end),
    run_tasks: $task_stages,
    validator_self_score: (if $self == "" then null else ($self | tonumber) end)
  }' > "$OUT/run-facts.json"

log "harvest complete → $OUT (run_id=${run_id:-none}, self_score=${self_score:-none})"
