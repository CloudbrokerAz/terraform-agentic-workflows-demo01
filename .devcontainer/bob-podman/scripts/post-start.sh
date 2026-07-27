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
# Probe the container runtime first, and probe it by actually RUNNING something
# -- `docker info` alone is not sufficient. On the amd64 image under Rosetta,
# `docker info` succeeds while `docker run` still fails, so an info-only probe
# reports success and then leaves the MCP server broken at use time.
#
# Both output streams are redirected because a failing probe can be noisy: under
# QEMU (rather than Rosetta) the bundled podman aborts during Go runtime init
# with "fatal error: lfstack.push" and dumps a ~100-line goroutine trace per
# invocation, which `|| true` does not suppress.
#
# This succeeds when the podman-machine socket is mounted (see the
# docker-outside-of-podman runArgs in ../../devcontainer.json), where `docker`
# creates sibling containers on the machine, and on a native arm64 host.
probe_runtime() {
    docker info >/dev/null 2>&1 || return 1
    # A real run: catches the case where the daemon answers but cannot start
    # containers. Uses an image already needed below, so it costs nothing extra.
    docker run --rm hashicorp/terraform-mcp-server:latest --help >/dev/null 2>&1
}

if probe_runtime; then
  docker image pull hashicorp/terraform-mcp-server:latest || true

  # Derived from the installed bobshell's package config so it tracks whatever
  # version the update above landed on.
  sandbox_image=$(node -p "require('$(npm root -g)/bobshell/package.json').config.sandboxImageUri" 2>/dev/null \
    || echo "docker.io/library/node:25-trixie")
  docker image pull "${sandbox_image}" || true
else
  echo "  Container runtime cannot start containers — skipping image pre-pulls"
  echo "  Terraform MCP server and Bob Shell's sandbox will not be available"
  echo "  Check the podman-machine socket mount in .devcontainer/devcontainer.json"
  echo "  (podman machine ssh <machine> 'echo \$XDG_RUNTIME_DIR/podman/podman.sock')"
fi

echo "=== Post-Start Complete ==="
