#!/usr/bin/env bash
# validate.sh — terraform validate over module dirs changed this turn.
# Runs `terraform init -backend=false` first (schemas only, no remote state).
# Exit 2 if any changed module fails validation; skips silently if terraform absent.
set -uo pipefail

command -v terraform >/dev/null 2>&1 || exit 0
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

# Directories containing a .tf file changed vs HEAD (tracked) or untracked.
changed="$(
  { git -C "$root" diff --name-only HEAD -- '*.tf' 2>/dev/null
    git -C "$root" ls-files --others --exclude-standard -- '*.tf' 2>/dev/null; }
)"
dirs="$(printf '%s\n' "$changed" | while IFS= read -r p; do
  [ -n "$p" ] && dirname "$p"
done | sort -u)"
[ -n "$dirs" ] || exit 0

rc=0
while IFS= read -r d; do
  [ -n "$d" ] && [ -d "$root/$d" ] || continue
  if ! ( cd "$root/$d" \
         && terraform init -backend=false -input=false >/dev/null 2>&1 \
         && terraform validate >/dev/null ); then
    echo "terraform validate failed in $d" >&2
    ( cd "$root/$d" && terraform validate 2>&1 | sed 's/^/  /' >&2 ) || true
    rc=2
  fi
done <<< "$dirs"
exit "$rc"
