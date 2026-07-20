#!/usr/bin/env bash
# PreToolUse guard: deny the agent from writing governance-protected config
# files. Wired identically into all three harnesses; each config's `matcher`
# restricts firing to write tools, so this script only checks the target path.
#
#   .claude/settings.json  -> PreToolUse, matcher "Write|Edit|MultiEdit|Update", arg "claude"
#   .agents/hooks/*.json    -> PreToolUse (PascalCase => Claude payload+matcher), arg "copilot"
#   .cursor/hooks.json      -> preToolUse, matcher "Write|Edit|MultiEdit|Update", arg "cursor"
#
# $1 = harness dialect, which selects the block exit code:
#   claude, cursor -> exit 2   (their documented "deny" signal)
#   copilot        -> exit 1   (Copilot denies on non-zero-EXCEPT-2; exit 2 is a
#                               warning-continue there, and timeouts fail open)
#
# The target path arrives under a "file_path"/"path"/"filePath" key in the JSON
# payload on stdin. JSON escaping (inner quotes become \") keeps this match
# anchored to the real argument, not filenames mentioned inside file content.
set -euo pipefail

if grep -qE '"(file_path|path|filePath)"[[:space:]]*:[[:space:]]*"([^"]*/)?\.(gitignore|tflint\.hcl|pre-commit-config\.yaml|mcp\.json)"'; then
  echo "BLOCKED: governance-protected config file; edit it manually if a change is genuinely required." >&2
  [ "${1:-}" = copilot ] && exit 1 || exit 2
fi
exit 0
