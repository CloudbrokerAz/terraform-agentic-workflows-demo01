#!/bin/bash
# Update Terraform to the latest version
set -euo pipefail

echo "=== Updating Terraform ==="

# Detect architecture (same pattern as terraform-tools.sh)
ARCH=$(uname -m)
if [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
    TF_ARCH="arm64"
else
    TF_ARCH="amd64"
fi

CURRENT=$(terraform version -json 2>/dev/null | jq -r '.terraform_version' 2>/dev/null || echo "unknown")

# Get latest version from HashiCorp checkpoint API
LATEST=$(curl -sSf https://checkpoint-api.hashicorp.com/v1/check/terraform | jq -r '.current_version')

if [ -z "$LATEST" ] || [ "$LATEST" = "null" ]; then
    echo "  Could not determine latest Terraform version, skipping update"
    exit 0
fi

if [ "$CURRENT" = "$LATEST" ]; then
    echo "  Terraform already at latest (v${CURRENT})"
    exit 0
fi

echo "  Updating Terraform: v${CURRENT} -> v${LATEST}..."
# Extract into a fresh temp dir, not /tmp directly: the terraform zip ships a
# LICENSE.txt, and a root-owned /tmp/LICENSE.txt left over from the base image
# build cannot be overwritten by the unprivileged `node` user (notably under
# Podman's --userns=keep-id), which would fail the whole update with
# "cannot delete old /tmp/LICENSE.txt: Operation not permitted".
TMP_TF_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_TF_DIR"' EXIT
curl -sSL -o "${TMP_TF_DIR}/terraform.zip" "https://releases.hashicorp.com/terraform/${LATEST}/terraform_${LATEST}_linux_${TF_ARCH}.zip"
unzip -qq -o "${TMP_TF_DIR}/terraform.zip" -d "${TMP_TF_DIR}"
sudo mv "${TMP_TF_DIR}/terraform" /usr/local/bin/terraform
echo "  Terraform updated to v${LATEST}"
