#!/bin/bash
# Post-create setup script for Copilot devcontainer
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

echo "=== Post-Create Setup Complete ==="
