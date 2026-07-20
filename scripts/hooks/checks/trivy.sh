#!/usr/bin/env bash
# trivy.sh — Trivy IaC (config) scan of the repo. Mirrors the severity/skip settings
# from the old .pre-commit-config.yaml. Exit 2 on findings; skips if trivy is absent.
set -uo pipefail

command -v trivy >/dev/null 2>&1 || exit 0
root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

if ! trivy config "$root" \
      --skip-dirs "**/.devcontainer" \
      --skip-dirs "**/.foundations" \
      --tf-exclude-downloaded-modules=true \
      --severity CRITICAL,HIGH,MEDIUM \
      --exit-code 2; then
  echo "trivy found IaC misconfigurations (see above)" >&2
  exit 2
fi
exit 0
