#!/bin/bash
# Post-create setup script for Bob devcontainer
set -e

echo "=== Post-Create Setup Starting ==="

SCRIPT_DIR="$(dirname "$0")"

# Configure token-authenticated HTTPS git auth and neutralize any global
# HTTPS->SSH insteadOf rewrite baked into the image (see issue #45).
"${SCRIPT_DIR}/../../scripts/setup-git-auth.sh" \
    || echo "Git auth setup failed; pushes may require manual git config"

# Fix permissions for command history volume
# Docker volumes are created with root ownership, but we run as 'node' user
if [ -d /commandhistory ]; then
  sudo chown -R node:node /commandhistory
  touch /commandhistory/.zsh_history
  touch /commandhistory/.bash_history
fi

# Configure Terraform credentials for HCP Terraform
echo "Configuring Terraform credentials..."
mkdir -p ~/.terraform.d
cat > ~/.terraform.d/credentials.tfrc.json << EOF
{
  "credentials": {
    "app.terraform.io": {
      "token": "${TFE_TOKEN}"
    }
  }
}
EOF
echo "Terraform credentials configured"

# Enable the native git hooks (commit-boundary checks: vault-radar, large-file,
# merge-conflict). Replaces the old pre-commit framework — see
# docs/proposals/agent-hooks-migration.md.
if [ -d .githooks ]; then
  git config core.hooksPath .githooks
  echo "git core.hooksPath set to .githooks"
fi

# Install the reference approval profile into the container.
#
# The bob-code extension declares no extensionKind, so it defaults to
# "workspace" and runs in the REMOTE extension host -- inside this container.
# It resolves its config as os.homedir() + "/.bob", i.e. /home/node/.bob here,
# NOT the developer's ~/.bob on the Mac. Approvals configured on the host
# therefore have no effect in the devcontainer, and every command prompts.
#
# Bob has no checked-in workspace-level approval file, so seeding the
# container's user-level config is the only way to ship this with the repo.
#
# Merges only the "approval" key so anything else Bob has written (notably
# "migrations", which it creates on first start) is preserved. Idempotent:
# post-create runs on every container start.
BOB_SETTINGS_EXAMPLE=".bob/settings.example.json"
BOB_SETTINGS_DEST="${HOME}/.bob/settings/settings.json"
if [ -f "${BOB_SETTINGS_EXAMPLE}" ]; then
  echo "Installing Bob approval profile..."
  mkdir -p "$(dirname "${BOB_SETTINGS_DEST}")"
  if python3 - "${BOB_SETTINGS_EXAMPLE}" "${BOB_SETTINGS_DEST}" <<'PY'
import json, sys, os
src, dest = sys.argv[1], sys.argv[2]
example = json.load(open(src))
current = {}
if os.path.exists(dest):
    try:
        current = json.load(open(dest))
    except (ValueError, OSError):
        current = {}          # unreadable/corrupt -> rewrite rather than fail
if "approval" not in example:
    sys.exit("  settings.example.json has no 'approval' key")
current["approval"] = example["approval"]
with open(dest, "w") as fh:
    json.dump(current, fh, indent=2)
    fh.write("\n")
ap = current["approval"]
print("  approval profile installed -> %s" % dest)
print("  autoApprovalEnabled=%s, %d permission groups, %d approved commands"
      % (ap.get("autoApprovalEnabled"),
         len(ap.get("allowed_permissions", [])),
         len(ap.get("allowedExecutors", [{}])[0].get("approvedCommands", []))))
PY
  then :; else echo "  Bob approval profile install failed; commands will prompt"; fi
else
  echo "  ${BOB_SETTINGS_EXAMPLE} not found; skipping Bob approval profile"
fi

echo "=== Post-Create Setup Complete ==="
