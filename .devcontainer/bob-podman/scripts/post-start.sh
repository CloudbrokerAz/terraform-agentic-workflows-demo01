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

# Pre-pull the images used by the Terraform MCP server and Bob Shell's sandbox.
#
# Probe the nested runtime first. `|| true` is not enough on its own: when this
# amd64 image runs under QEMU emulation (Apple Silicon host, see
# ../../bob-podman-amd64/Dockerfile), the bundled podman binary aborts during Go
# runtime init with
#   runtime: lfstack.push invalid packing: node=0x... -> node=0xffffffff...
#   fatal error: lfstack.push
# and dumps a ~100-line goroutine trace per invocation. Go packs pointers into
# 48 bits assuming Linux x86-64 userspace addresses; QEMU hands out addresses
# above that range. Redirecting the probe keeps that trace out of the log.
#
# On a native arm64 host podman works, the probe succeeds, and the pulls run
# exactly as before.
if docker info >/dev/null 2>&1; then
  docker image pull hashicorp/terraform-mcp-server:latest || true

  # Derived from the installed bobshell's package config so it tracks whatever
  # version the update above landed on.
  sandbox_image=$(node -p "require('$(npm root -g)/bobshell/package.json').config.sandboxImageUri" 2>/dev/null \
    || echo "docker.io/library/node:25-trixie")
  docker image pull "${sandbox_image}" || true
else
  echo "  Container runtime unavailable (emulated arch?) — skipping image pre-pulls"
  echo "  Terraform MCP server and Bob Shell's sandbox will not be available"
fi

echo "=== Post-Start Complete ==="
