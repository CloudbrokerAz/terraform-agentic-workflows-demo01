#!/bin/bash
set -euo pipefail
echo "=== Post-Start: Updating Tools ==="

# Update IBM Bob Shell to the latest published version (same version source
# the official install-bobshell.sh uses). Timeouts bound the stall when the
# COS endpoint is blackholed rather than refusing.
echo "Updating Bob Shell..."
version=$(curl -fsSL --connect-timeout 10 --max-time 30 https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-version.txt || true)
if [ -n "${version}" ]; then
  npm install -g "https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-${version}.tgz" 2>/dev/null \
    || echo "  Bob Shell update skipped"
else
  echo "  Bob Shell version lookup failed; update skipped"
fi

# Update Terraform
SCRIPT_DIR="$(dirname "$0")"
"${SCRIPT_DIR}/../../scripts/update-terraform.sh" || echo "  Terraform update skipped"

# Pull latest Terraform MCP server image (existing behavior)
docker image pull hashicorp/terraform-mcp-server:latest || true

# Pre-pull Bob Shell's sandbox image, derived from the installed bobshell's
# package config so it tracks whatever version the update above landed on.
sandbox_image=$(node -p "require('$(npm root -g)/bobshell/package.json').config.sandboxImageUri" 2>/dev/null \
  || echo "docker.io/library/node:25-trixie")
docker image pull "${sandbox_image}" || true

echo "=== Post-Start Complete ==="
