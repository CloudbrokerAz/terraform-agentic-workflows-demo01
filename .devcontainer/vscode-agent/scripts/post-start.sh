#!/bin/bash
set -euo pipefail
echo "=== Post-Start: Updating Tools ==="

# Update GitHub Copilot CLI
echo "Updating GitHub Copilot..."
npm install -g @github/copilot@latest 2>/dev/null || echo "  Copilot update skipped"

# Update Terraform
SCRIPT_DIR="$(dirname "$0")"
"${SCRIPT_DIR}/../../scripts/update-terraform.sh" || echo "  Terraform update skipped"

# Pull latest Terraform MCP server image (existing behavior)
docker image pull hashicorp/terraform-mcp-server:latest || true

echo "=== Post-Start Complete ==="
