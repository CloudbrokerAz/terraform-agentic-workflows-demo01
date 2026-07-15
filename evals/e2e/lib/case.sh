#!/usr/bin/env bash
# Case parsing and placeholder substitution. Sourced after common.sh.

# case_get <case_file> <jq_expr> — raw output, empty string for null.
case_get() {
  jq -r "$2 // empty" "$1"
}

# Render the case's prompt fixture with run-unique substitutions.
# <GITHUB_REPO_NAME> in prompts and {SUFFIX} in workspace_pattern receive the SAME
# value, so the runner knows the workspace name before the agent ever runs.
# render_prompt <case_file> <suffix> <out_file>
render_prompt() {
  local case_file=$1 suffix=$2 out=$3
  local prompt_rel prompt_abs
  prompt_rel=$(case_get "$case_file" '.prompt_file')
  prompt_abs="$REPO_ROOT/$prompt_rel"
  [[ -f "$prompt_abs" ]] || die "prompt_file not found: $prompt_abs"
  sed "s/<GITHUB_REPO_NAME>/$suffix/g" "$prompt_abs" > "$out"
  if grep -q '<GITHUB_REPO_NAME>' "$out"; then
    die "placeholder <GITHUB_REPO_NAME> survived substitution in $out"
  fi
}

# workspace_name <case_file> <suffix> — empty if the case doesn't deploy.
workspace_name() {
  local case_file=$1 suffix=$2 pattern
  pattern=$(case_get "$case_file" '.sandbox.workspace_pattern')
  [[ -n "$pattern" ]] || return 0
  printf '%s' "${pattern//\{SUFFIX\}/$suffix}"
}

# case_requires_deploy <case_file> — exit 0 if sandbox.deploy == true.
case_requires_deploy() {
  [[ "$(jq -r '.sandbox.deploy' "$1")" == "true" ]]
}
