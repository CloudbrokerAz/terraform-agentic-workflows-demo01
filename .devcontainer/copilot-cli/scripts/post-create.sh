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

# Initialize pre-commit hooks
if [ -f .pre-commit-config.yaml ]; then
  echo "Installing pre-commit hooks..."
  pre-commit install
  echo "Pre-commit hooks installed"
fi

echo "=== Post-Create Setup Complete ==="
