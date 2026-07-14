#!/usr/bin/env bash
# hygiene.sh — commit-boundary file hygiene over the STAGED set:
#   * large-file guard  (default 500 KB, override with TF_GUARD_MAXKB)
#   * merge-conflict markers
# Exit 1 on any violation (aborts the commit).
set -uo pipefail

root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
maxkb="${TF_GUARD_MAXKB:-500}"
rc=0

staged="$(git -C "$root" diff --cached --name-only --diff-filter=AM 2>/dev/null)"
[ -n "$staged" ] || exit 0

while IFS= read -r f; do
  [ -n "$f" ] && [ -f "$root/$f" ] || continue

  bytes="$(wc -c < "$root/$f" | tr -d ' ')"
  kb=$(( (bytes + 1023) / 1024 ))
  if [ "$kb" -gt "$maxkb" ]; then
    echo "Large file staged: $f (${kb}KB > ${maxkb}KB)" >&2
    rc=1
  fi

  if grep -qE '^(<<<<<<< |=======$|>>>>>>> )' "$root/$f" 2>/dev/null; then
    echo "Merge-conflict marker in $f" >&2
    rc=1
  fi
done <<< "$staged"
exit "$rc"
