#!/usr/bin/env bash
set -euo pipefail

# Checks for CRD breaking changes after regeneration.
# Exits non-zero if breaking changes are detected.
# Usage: check-breaking-changes.sh <service-name> [workspace-path]
# Example: check-breaking-changes.sh ec2

SERVICE="$1"
WORKSPACE="${2:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
CODEGEN_DIR="${WORKSPACE}/code-generator"
CONTROLLER_DIR="${WORKSPACE}/${SERVICE}-controller"

if [[ ! -d "${CODEGEN_DIR}" ]]; then
  echo "ERROR: code-generator not found at ${CODEGEN_DIR}" >&2
  exit 1
fi

if [[ ! -d "${CONTROLLER_DIR}" ]]; then
  echo "ERROR: ${SERVICE}-controller not found at ${CONTROLLER_DIR}" >&2
  exit 1
fi

CRD_PATHS="${CONTROLLER_DIR}/config/crd/bases,${CONTROLLER_DIR}/helm/crds"

echo "Checking CRD compatibility for ${SERVICE}..."
cd "${CODEGEN_DIR}"

if ! make check-crd-compatibility CRD_PATHS="${CRD_PATHS}"; then
  echo ""
  echo "BREAKING CHANGE DETECTED in ${SERVICE}-controller CRDs."
  echo "You must revert and consult the user before proceeding."
  echo "  Revert: cd ${CONTROLLER_DIR} && git checkout -- ."
  exit 1
fi

echo "No breaking changes detected."
