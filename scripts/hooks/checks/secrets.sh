#!/usr/bin/env bash
# secrets.sh — secret scanning at two boundaries.
#
#   secrets.sh privatekey   end-of-turn regex scan of changed files for private-key
#                           blocks. Exit 2 on a hit.
#   secrets.sh vaultradar   commit-boundary Vault Radar scan (its first-class client
#                           mode). Skips if unlicensed or the CLI is absent. Exit 1 on
#                           a finding (aborts the commit).
set -uo pipefail

sub="${1:-}"
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

case "$sub" in
  privatekey)
    changed="$(
      { git -C "$root" diff --name-only HEAD 2>/dev/null
        git -C "$root" ls-files --others --exclude-standard 2>/dev/null; } | sort -u
    )"
    [ -n "$changed" ] || exit 0
    hit=0
    while IFS= read -r f; do
      [ -n "$f" ] && [ -f "$root/$f" ] || continue
      if grep -qE 'BEGIN [A-Z0-9 ]*PRIVATE KEY' "$root/$f" 2>/dev/null; then
        echo "Possible private key in $f" >&2
        hit=1
      fi
    done <<< "$changed"
    [ "$hit" -eq 0 ] || exit 2
    ;;

  vaultradar)
    if [ -z "${VAULT_RADAR_LICENSE:-}" ]; then
      echo "Vault Radar scan skipped (VAULT_RADAR_LICENSE not set)"
      exit 0
    fi
    if ! command -v vault-radar >/dev/null 2>&1; then
      echo "Vault Radar scan skipped (vault-radar not installed)"
      exit 0
    fi
    vault-radar scan git pre-commit || exit "$?"
    ;;

  *)
    echo "secrets.sh: unknown subcommand '${sub}' (expected privatekey|vaultradar)" >&2
    exit 0
    ;;
esac
