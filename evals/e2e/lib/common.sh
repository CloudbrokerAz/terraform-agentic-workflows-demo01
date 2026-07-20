#!/usr/bin/env bash
# Shared helpers for the e2e eval framework. Bash/zsh compatible (sourced).

EVAL_ROOT="${EVAL_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)}"
REPO_ROOT="${REPO_ROOT:-$(cd "$EVAL_ROOT/../.." && pwd)}"

log()  { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
warn() { printf '[%s] WARN: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; }
die()  { printf '[%s] ERROR: %s\n' "$(date -u +%H:%M:%S)" "$*" >&2; exit 1; }

# Load evals/e2e/.env if present (never committed).
load_env() {
  if [[ -f "$EVAL_ROOT/.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$EVAL_ROOT/.env"
    set +a
  fi
}

# Run-unique id: 20260708T213000Z-ab12
new_run_id() {
  printf '%s-%s' "$(date -u +%Y%m%dT%H%M%SZ)" "$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' | cut -c1-4)"
}

# Suffix used for both {SUFFIX} in workspace_pattern and <GITHUB_REPO_NAME> in prompts.
# Lowercase alnum + leading underscore, short enough for TFE workspace names.
suffix_from_run_id() {
  printf '_%s' "$(printf '%s' "$1" | tr -cd 'a-z0-9' | tail -c 8)"
}

# retry <n> <sleep_base_seconds> <cmd...> — exponential backoff.
retry() {
  local -i tries=$1 base=$2 i=0; shift 2
  local delay
  while true; do
    "$@" && return 0
    i=$((i + 1))
    (( i >= tries )) && return 1
    delay=$((base * (2 ** (i - 1))))
    warn "retry $i/$tries in ${delay}s: $*"
    sleep "$delay"
  done
}

# TFE API helper. Usage: tfe_api GET /organizations/org/workspaces/name
tfe_api() {
  local method=$1 path=$2 body=${3:-}
  local addr="${TFE_ADDR:-https://app.terraform.io}"
  [[ -n "${TFE_TOKEN:-}" ]] || die "TFE_TOKEN not set"
  local args=(-sS -X "$method"
    -H "Authorization: Bearer $TFE_TOKEN"
    -H "Content-Type: application/vnd.api+json"
    "$addr/api/v2$path")
  if [[ -n "$body" ]]; then args+=(-d "$body"); fi
  curl "${args[@]}"
}

# Like tfe_api, but also exposes the HTTP status in TFE_HTTP_CODE so callers
# can tell "404 not found" apart from "network/auth failure" (which must never
# be treated as success). Returns non-zero on transport errors (code 000).
tfe_api_with_code() {
  local method=$1 path=$2 body=${3:-}
  local addr="${TFE_ADDR:-https://app.terraform.io}"
  [[ -n "${TFE_TOKEN:-}" ]] || die "TFE_TOKEN not set"
  local args=(-sS -X "$method"
    -H "Authorization: Bearer $TFE_TOKEN"
    -H "Content-Type: application/vnd.api+json"
    -w $'\n%{http_code}'
    "$addr/api/v2$path")
  if [[ -n "$body" ]]; then args+=(-d "$body"); fi
  local out
  if ! out=$(curl "${args[@]}" 2>/dev/null); then
    TFE_HTTP_CODE=000
    return 1
  fi
  TFE_HTTP_CODE=${out##*$'\n'}
  printf '%s' "${out%$'\n'*}"
}

# Append one JSON line to a shared file safely under parallelism.
# flock where available (Linux/Docker); mkdir spinlock on stock macOS.
append_jsonl() {
  local file=$1 line=$2
  mkdir -p "$(dirname "$file")"
  if command -v flock >/dev/null; then
    (
      flock -w 30 9 || die "flock timeout on $file"
      printf '%s\n' "$line" >&9
    ) 9>>"$file"
  else
    local lock="$file.lock" i=0
    until mkdir "$lock" 2>/dev/null; do
      i=$((i + 1))
      (( i > 300 )) && die "lock timeout on $file"
      sleep 0.1
    done
    printf '%s\n' "$line" >> "$file"
    rmdir "$lock"
  fi
}

# Portable timeout: GNU timeout (Linux/Docker), gtimeout (brew coreutils),
# else a pure-bash watchdog (TERM after N secs, KILL 60s later). Watchdog
# kills return 143 rather than GNU timeout's 124.
run_with_timeout() {
  local secs=$1; shift
  if command -v timeout >/dev/null; then
    timeout --kill-after=60 "$secs" "$@"
  elif command -v gtimeout >/dev/null; then
    gtimeout --kill-after=60 "$secs" "$@"
  else
    local cmd_pid watch_pid rc
    "$@" & cmd_pid=$!
    ( sleep "$secs"; kill -TERM "$cmd_pid" 2>/dev/null; sleep 60; kill -KILL "$cmd_pid" 2>/dev/null ) &
    watch_pid=$!
    wait "$cmd_pid"; rc=$?
    kill "$watch_pid" 2>/dev/null
    wait "$watch_pid" 2>/dev/null
    return "$rc"
  fi
}
