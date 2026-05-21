#!/usr/bin/env bash
set -euo pipefail

# Regenerates a controller using the code-generator.
# Usage: regenerate.sh <service-name> [workspace-path]
# Example: regenerate.sh ec2

SERVICE="$1"
WORKSPACE="${2:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
CODEGEN_DIR="${WORKSPACE}/code-generator"

export PATH="${HOME}/go/bin:${PATH}"

if [[ ! -d "${CODEGEN_DIR}" ]]; then
  echo "ERROR: code-generator not found at ${CODEGEN_DIR}" >&2
  echo "Run ensure-repo.sh first." >&2
  exit 1
fi

echo "Regenerating ${SERVICE} controller..."
cd "${CODEGEN_DIR}"
make build-controller SERVICE="${SERVICE}"
echo "Regeneration complete for ${SERVICE}."
