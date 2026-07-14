#!/usr/bin/env bash
# lint.sh — tflint over module dirs changed this turn, using the repo .tflint.hcl.
# Exit 2 on any finding; skips silently if tflint is absent.
set -uo pipefail

command -v tflint >/dev/null 2>&1 || exit 0
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cfg="$root/.tflint.hcl"

changed="$(
  { git -C "$root" diff --name-only HEAD -- '*.tf' 2>/dev/null
    git -C "$root" ls-files --others --exclude-standard -- '*.tf' 2>/dev/null; }
)"
dirs="$(printf '%s\n' "$changed" | while IFS= read -r p; do
  [ -n "$p" ] && dirname "$p"
done | sort -u)"
[ -n "$dirs" ] || exit 0

# Download configured plugins once (no-op if already present).
tflint --init >/dev/null 2>&1 || true

rc=0
while IFS= read -r d; do
  [ -n "$d" ] && [ -d "$root/$d" ] || continue
  if [ -f "$cfg" ]; then
    ( cd "$root/$d" && tflint --config="$cfg" ) || { echo "tflint findings in $d" >&2; rc=2; }
  else
    ( cd "$root/$d" && tflint ) || { echo "tflint findings in $d" >&2; rc=2; }
  fi
done <<< "$dirs"
exit "$rc"
