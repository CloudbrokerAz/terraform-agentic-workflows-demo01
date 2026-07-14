#!/usr/bin/env bash
# fmt.sh — deterministic formatting mutations. NEVER errors (always exit 0).
#
#   fmt.sh <file>        terraform fmt the file + terraform-docs its module dir
#   fmt.sh --eof <file>  ensure the file ends with exactly one trailing newline
set -uo pipefail

if [ "${1:-}" = "--eof" ]; then
  f="${2:-}"
  [ -f "$f" ] || exit 0
  # Append a newline only if the last byte isn't one.
  if [ -s "$f" ] && [ -n "$(tail -c1 "$f")" ]; then
    printf '\n' >> "$f"
  fi
  exit 0
fi

f="${1:-}"
[ -f "$f" ] || exit 0

case "$f" in
  *.tf|*.tfvars)
    if command -v terraform >/dev/null 2>&1; then
      terraform fmt "$f" >/dev/null 2>&1 || true
    fi
    # Regenerate the module README (directory-scoped). Config, if any, comes from
    # a .terraform-docs.yml in the module dir; otherwise inject into README.md.
    if command -v terraform-docs >/dev/null 2>&1; then
      dir="$(dirname "$f")"
      if [ -f "$dir/README.md" ]; then
        terraform-docs markdown table --output-file README.md \
          --output-mode inject "$dir" >/dev/null 2>&1 || true
      fi
    fi
    ;;
esac

exit 0
