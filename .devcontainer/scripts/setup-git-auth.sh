#!/bin/bash
# Git authentication setup for DevContainers / agent runners.
#
# Fixes hashi-demo-lab/terraform-agentic-workflows#45.
#
# The base/runner image carries a global (or system) git rewrite rule of the form
#
#     [url "git@github.com:"]
#         insteadOf = https://github.com/
#
# which silently rewrites every `https://github.com/...` remote to SSH. In an
# agent/CI environment there is no SSH key, so token-authenticated HTTPS pushes
# fail (or hang on a host-key / auth prompt). This script:
#
#   1. Neutralizes any GitHub HTTPS->SSH `insteadOf` rewrite (global + system).
#   2. Standardizes on token-authenticated HTTPS using GITHUB_TOKEN / GH_TOKEN,
#      with the token resolved from the environment at push time (never written
#      to ~/.gitconfig in plaintext).
#
# Idempotent and safe to re-run. Never aborts container setup: all failures are
# tolerated and the script always exits 0.
set -uo pipefail

echo "=== Git Auth Setup ==="

# --- 1. Neutralize GitHub HTTPS -> SSH rewrites ----------------------------
# Surgically drop only the insteadOf values that map a github HTTPS prefix onto
# an SSH transport, at both --global and --system scope. The value argument is a
# regex, so unrelated shorthands under the same url.<ssh> key are left intact.
GH_HTTPS_PATTERN='^https?://github\.com/'
for ssh_prefix in 'git@github.com:' 'ssh://git@github.com/'; do
    git config --global --unset-all "url.${ssh_prefix}.insteadOf" "$GH_HTTPS_PATTERN" 2>/dev/null || true
    sudo git config --system --unset-all "url.${ssh_prefix}.insteadOf" "$GH_HTTPS_PATTERN" 2>/dev/null || true
done
echo "  Cleared any github.com HTTPS->SSH insteadOf rewrites"

# --- 2. Token-authenticated HTTPS for github.com ---------------------------
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -z "$TOKEN" ]; then
    echo "  No GITHUB_TOKEN/GH_TOKEN in environment; skipping token auth setup"
    echo "=== Git Auth Setup Complete ==="
    exit 0
fi

configured=0

# Preferred: let gh act as the credential helper. The token is read from the
# environment on each call, so nothing secret lands in ~/.gitconfig.
if command -v gh > /dev/null 2>&1; then
    if GH_TOKEN="$TOKEN" gh auth setup-git --hostname github.com 2>/dev/null; then
        configured=1
        echo "  github.com HTTPS auth -> gh credential helper (token from env)"
    fi
fi

# Fallback: an inline credential helper that echoes the env token on `get`.
# Still keeps the token out of the config file (only the helper script is stored).
if [ "$configured" -eq 0 ]; then
    git config --global --replace-all credential."https://github.com".helper \
        '!f() { test "$1" = get && printf "username=x-access-token\npassword=%s\n" "${GITHUB_TOKEN:-${GH_TOKEN}}"; }; f'
    echo "  github.com HTTPS auth -> inline token credential helper (token from env)"
fi

echo "=== Git Auth Setup Complete ==="
exit 0
