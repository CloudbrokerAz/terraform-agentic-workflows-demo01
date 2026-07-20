#!/usr/bin/env bash
# link-foundations.sh — Point a consuming repo's ./.foundations at the plugin's
# own versioned copy in the harness plugin cache, without duplicating content.
#
# The plugin's skills, agents, and scripts reference `.foundations/…` as bare,
# repo-relative paths. When the plugin is installed into a consuming repo those
# paths resolve against the consumer's cwd, where `.foundations/` doesn't exist.
# This script creates a gitignored symlink `.foundations -> $ROOT/.foundations`
# so every existing bare reference resolves to the installed, versioned copy.
#
# It is invoked by a session-start hook in each harness, where the plugin-root
# environment variable is reliably available:
#   Claude Code — CLAUDE_PLUGIN_ROOT
#   Copilot CLI — PLUGIN_ROOT
#   Cursor      — CURSOR_PLUGIN_ROOT
#
# Idempotent and non-destructive:
#   * a real (non-symlink) .foundations dir is left untouched (template-repo
#     usage, or an org that deliberately vendored + tailored it);
#   * an existing symlink is refreshed only if it points somewhere else
#     (e.g. after a plugin upgrade moved the cache dir).
#
# Exit 0 in every non-error path so it never blocks a session start.

set -euo pipefail

log() { [[ -n "${LINK_FOUNDATIONS_VERBOSE:-}" ]] && printf 'link-foundations: %s\n' "$*" >&2 || true; }

# --- resolve the plugin root (versioned cache) ------------------------------
# Primary: self-location. A bundled script always knows where it lives — on any
# harness, with no dependency on a plugin-root env var (Cursor doesn't expose
# one). This file ships at <plugin_root>/scripts/link-foundations.sh, so the
# plugin root is its parent's parent. Env vars are honored first only as an
# override for indirect invocations.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${CLAUDE_PLUGIN_ROOT:-${PLUGIN_ROOT:-${CURSOR_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}}}"

SRC="$ROOT/.foundations"
if [[ ! -d "$SRC" ]]; then
  log "plugin root '$ROOT' has no .foundations/ — nothing to link"
  exit 0
fi

# --- resolve the destination (consuming repo root) --------------------------
# Prefer an explicit project-dir handed in by the harness/hook; fall back to an
# argument, then cwd. (Cursor is known to run plugin hooks with an inconsistent
# cwd, so an explicit dir is preferred when available. CLAUDE_PROJECT_DIR is set
# by both Claude Code and Cursor; CURSOR_PROJECT_DIR is Cursor-only.)
DEST_DIR="${CLAUDE_PROJECT_DIR:-${CURSOR_PROJECT_DIR:-${1:-$PWD}}}"
DEST="$DEST_DIR/.foundations"

# In the template repo / dev checkout, the bundled .foundations *is* the target:
# source and destination resolve to the same path. Nothing to link.
if [[ "$SRC" -ef "$DEST" ]] 2>/dev/null; then
  log "source and destination are the same path ($SRC); nothing to link"
  exit 0
fi

# --- create / refresh the link ----------------------------------------------
if [[ -L "$DEST" ]]; then
  current="$(readlink "$DEST" || true)"
  if [[ "$current" == "$SRC" ]]; then
    log "symlink already current -> $SRC"
    exit 0
  fi
  log "refreshing stale symlink ($current -> $SRC)"
  rm -f "$DEST"
elif [[ -e "$DEST" ]]; then
  # A real file or directory lives here — never clobber it.
  log "real .foundations exists at $DEST; leaving it untouched"
  exit 0
fi

# Keep the symlink out of the consuming repo's tracked git status without
# editing a committed .gitignore — use the repo-local, uncommitted
# .git/info/exclude. No-op outside a git repo or if already excluded.
add_git_exclude() {
  local dir="$1" gitdir exclude
  gitdir="$(git -C "$dir" rev-parse --git-dir 2>/dev/null)" || return 0
  case "$gitdir" in /*) ;; *) gitdir="$dir/$gitdir" ;; esac
  exclude="$gitdir/info/exclude"
  mkdir -p "$gitdir/info" 2>/dev/null || return 0
  if [[ -f "$exclude" ]] && grep -qxF ".foundations" "$exclude" 2>/dev/null; then
    return 0
  fi
  printf '.foundations\n' >>"$exclude" 2>/dev/null || true
  log "excluded .foundations via $exclude"
}

if ln -s "$SRC" "$DEST" 2>/dev/null; then
  log "linked $DEST -> $SRC"
  add_git_exclude "$DEST_DIR"
else
  # Symlinks can be unavailable (some Windows setups). Leave the tree untouched;
  # the manual `:init` fallback covers this case.
  log "could not create symlink at $DEST (unsupported?); run /tf-workflows:init to copy instead"
fi
exit 0
