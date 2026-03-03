#!/usr/bin/env bash
# Build an ACK service controller using the code-generator.
# Usage: build-controller.sh <service> [aws-sdk-go-version] [code-generator-path]
#
# Examples:
#   build-controller.sh ecr
#   build-controller.sh backup v1.41.0
#   build-controller.sh s3 v1.41.0 /home/user/code-generator

set -euo pipefail

SERVICE="${1:?Usage: build-controller.sh <service> [aws-sdk-go-version] [code-generator-path]}"
AWS_SDK_GO_VERSION="${2:-v1.41.0}"
CODEGEN_DIR="${3:-}"

# Find code-generator directory
if [[ -n "$CODEGEN_DIR" ]]; then
    true
elif [[ -d "../code-generator" ]]; then
    CODEGEN_DIR="../code-generator"
elif [[ -d "../../code-generator" ]]; then
    CODEGEN_DIR="../../code-generator"
else
    echo "ERROR: Cannot find code-generator directory. Pass it as the third argument." >&2
    exit 1
fi

CODEGEN_DIR="$(cd "$CODEGEN_DIR" && pwd)"

# Verify ack-generate binary exists
if [[ ! -f "$CODEGEN_DIR/bin/ack-generate" ]]; then
    echo "Building ack-generate first..."
    make -C "$CODEGEN_DIR" build-ack-generate
fi

echo "Building $SERVICE controller (SDK $AWS_SDK_GO_VERSION) using $CODEGEN_DIR"
SERVICE="$SERVICE" AWS_SDK_GO_VERSION="$AWS_SDK_GO_VERSION" make -C "$CODEGEN_DIR" build-controller

echo ""
echo "Build complete. Run verify-build.sh to check generated files."
