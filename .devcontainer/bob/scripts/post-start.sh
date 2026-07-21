#!/bin/bash
set -euo pipefail
echo "=== Post-Start: Updating Tools ==="

# Update IBM Bob Shell to the latest published version (same version source
# the official install-bobshell.sh uses).
echo "Updating Bob Shell..."
version=$(curl -fsSL https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-version.txt || true)
if [ -n "${version}" ]; then
  npm install -g "https://s3.us-south.cloud-object-storage.appdomain.cloud/bobshell/bobshell-${version}.tgz" 2>/dev/null \
    || echo "  Bob Shell update skipped"
else
  echo "  Bob Shell version lookup failed; update skipped"
fi

# Update Terraform
SCRIPT_DIR="$(dirname "$0")"
"${SCRIPT_DIR}/../../scripts/update-terraform.sh"

# Pull latest Terraform MCP server image (existing behavior)
docker image pull hashicorp/terraform-mcp-server:latest || true

# Pre-pull Bob Shell's sandbox image (bobshell package.json sandboxImageUri)
docker image pull docker.io/library/node:25-trixie || true

echo "=== Post-Start Complete ==="
