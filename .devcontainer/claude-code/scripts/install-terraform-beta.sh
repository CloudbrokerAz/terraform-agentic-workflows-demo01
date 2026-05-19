#!/bin/bash
# Install beta Terraform from a local zip in /workspace/reference/.
# Portable across macOS and Linux: detects OS+arch and picks the matching zip.
# Caller is responsible for gating this on TERRAFORM_BETA=true.
set -euo pipefail

REF_DIR="${TERRAFORM_BETA_REF_DIR:-/workspace/reference}"
INSTALL_PATH="/usr/local/bin/terraform"
BACKUP_PATH="/usr/local/bin/terraform.stable"

case "$(uname -s)" in
    Darwin) OS="darwin" ;;
    Linux)  OS="linux" ;;
    *) echo "install-terraform-beta: unsupported OS $(uname -s)" >&2; exit 1 ;;
esac

case "$(uname -m)" in
    arm64|aarch64) ARCH="arm64" ;;
    x86_64|amd64)  ARCH="amd64" ;;
    *) echo "install-terraform-beta: unsupported arch $(uname -m)" >&2; exit 1 ;;
esac

shopt -s nullglob
matches=( "${REF_DIR}"/terraform_*_${OS}_${ARCH}*.zip )
shopt -u nullglob

if [ ${#matches[@]} -eq 0 ]; then
    echo "install-terraform-beta: no matching zip at ${REF_DIR}/terraform_*_${OS}_${ARCH}*.zip" >&2
    exit 1
fi
ZIP="${matches[0]}"
echo "install-terraform-beta: using ${ZIP}"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

unzip -q "${ZIP}" -d "${TMP}"
if [ ! -f "${TMP}/terraform" ]; then
    echo "install-terraform-beta: terraform binary not found inside zip" >&2
    exit 1
fi
chmod +x "${TMP}/terraform"

# Strip macOS Gatekeeper quarantine if present (no-op on Linux / missing attr).
if [ "${OS}" = "darwin" ]; then
    xattr -d com.apple.quarantine "${TMP}/terraform" 2>/dev/null || true
fi

# Back up the existing terraform once. Don't overwrite a prior backup, so
# repeated runs don't end up backing up the beta over the real stable copy.
if [ -f "${INSTALL_PATH}" ] && [ ! -f "${BACKUP_PATH}" ]; then
    sudo mv "${INSTALL_PATH}" "${BACKUP_PATH}"
    echo "install-terraform-beta: backed up existing terraform to ${BACKUP_PATH}"
fi

sudo install -m 0755 "${TMP}/terraform" "${INSTALL_PATH}"
echo "install-terraform-beta: installed $("${INSTALL_PATH}" version | head -1)"
