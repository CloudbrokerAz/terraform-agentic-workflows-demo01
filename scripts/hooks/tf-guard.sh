#!/usr/bin/env bash
# tf-guard.sh — shared hook dispatcher for Claude Code, GitHub Copilot, and the
# native git pre-commit hook. One source of truth for the checks that used to live
# in .pre-commit-config.yaml. See docs/proposals/agent-hooks-migration.md.
#
# Modes:
#   fix     — per-file, post-write (PostToolUse / postToolUse):
#             terraform fmt + terraform-docs + EOF newline (mutations, never error);
#             YAML syntax (exit 2 on parse error → fed back to the agent).
#   verify  — end of turn (Stop / agentStop):
#             terraform validate + tflint + trivy + private-key scan over changed dirs.
#   commit  — native git pre-commit:
#             vault-radar + large-file guard + merge-conflict markers over the staged set.
#
# Reads the agent hook payload (JSON) on stdin when present; the git hook passes none.
set -uo pipefail

MODE="${1:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHECKS="$HERE/checks"
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT" || exit 0

# stdin may be a Claude/Copilot hook payload, or empty (Stop / git hook).
STDIN_JSON=""
if [ ! -t 0 ]; then STDIN_JSON="$(cat 2>/dev/null || true)"; fi

# Extract the edited file path from either a Claude or a Copilot payload.
hook_file_path() {
  [ -n "$STDIN_JSON" ] || return 0
  printf '%s' "$STDIN_JSON" | python3 -c '
import sys, json
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
def dig(o, *ks):
    for k in ks:
        if isinstance(o, dict) and k in o:
            o = o[k]
        else:
            return None
    return o
for p in (dig(d,"tool_input","file_path"),
          dig(d,"tool_input","path"),
          dig(d,"toolInput","path"),
          dig(d,"toolInput","file_path"),
          dig(d,"arguments","path"),
          dig(d,"input","file_path")):
    if isinstance(p, str) and p:
        print(p); break
' 2>/dev/null || true
}

case "$MODE" in
  fix)
    f="$(hook_file_path)"
    [ -n "$f" ] || exit 0            # no path in payload → nothing to fix
    [ -f "$f" ] || exit 0
    rc=0
    case "$f" in
      *.tf|*.tfvars) "$CHECKS/fmt.sh" "$f" || true ;;
      *.yaml|*.yml)  "$CHECKS/yaml.sh" "$f" || rc=$? ;;
    esac
    "$CHECKS/fmt.sh" --eof "$f" || true
    exit "$rc"
    ;;

  verify)
    rc=0
    "$CHECKS/validate.sh" || rc=2
    "$CHECKS/lint.sh"     || rc=2
    "$CHECKS/trivy.sh"    || rc=2
    "$CHECKS/secrets.sh" privatekey || rc=2
    exit "$rc"
    ;;

  commit)
    rc=0
    "$CHECKS/secrets.sh" vaultradar || rc=1
    "$CHECKS/hygiene.sh"            || rc=1
    exit "$rc"
    ;;

  *)
    echo "tf-guard.sh: unknown mode '${MODE}' (expected fix|verify|commit)" >&2
    exit 0
    ;;
esac
