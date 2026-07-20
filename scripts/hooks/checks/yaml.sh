#!/usr/bin/env bash
# yaml.sh — YAML syntax check for a single file.
# Exit 2 on a parse error (fed back to the agent); exit 0 otherwise.
# Skips silently if no YAML parser is available (never a false failure).
set -uo pipefail

f="${1:-}"
[ -f "$f" ] || exit 0

err="$(python3 -c '
import sys
try:
    import yaml
except ImportError:
    sys.exit(0)
try:
    with open(sys.argv[1]) as fh:
        list(yaml.safe_load_all(fh))
except Exception as e:
    print(e)
    sys.exit(3)
' "$f" 2>&1)"
status=$?

if [ "$status" -eq 3 ]; then
  echo "YAML parse error in $f:" >&2
  echo "$err" >&2
  exit 2
fi
exit 0
