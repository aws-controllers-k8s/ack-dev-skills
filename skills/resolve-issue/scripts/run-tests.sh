#!/usr/bin/env bash
set -euo pipefail

# Runs unit tests for a controller.
# Usage: run-tests.sh <service-name> [workspace-path]
# Example: run-tests.sh ec2

SERVICE="$1"
WORKSPACE="${2:-$(cd "$(dirname "$0")/../../../.." && pwd)}"
CONTROLLER_DIR="${WORKSPACE}/${SERVICE}-controller"

if [[ ! -d "${CONTROLLER_DIR}" ]]; then
  echo "ERROR: ${SERVICE}-controller not found at ${CONTROLLER_DIR}" >&2
  exit 1
fi

echo "Running tests for ${SERVICE}-controller..."
cd "${CONTROLLER_DIR}"
make test
echo "All tests passed for ${SERVICE}-controller."
