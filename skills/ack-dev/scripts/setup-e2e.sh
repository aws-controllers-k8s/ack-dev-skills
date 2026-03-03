#!/usr/bin/env bash
# Set up E2E test environment for an ACK service controller.
# Run from the service controller directory.
# Usage: setup-e2e.sh

set -euo pipefail

if [[ ! -d "test/e2e" ]]; then
    echo "ERROR: No test/e2e directory found. Are you in a controller repo?" >&2
    exit 1
fi

if [[ ! -f "test/e2e/requirements.txt" ]]; then
    echo "ERROR: test/e2e/requirements.txt not found." >&2
    exit 1
fi

# Create or refresh venv
if [[ -d "test/e2e/.venv" ]]; then
    echo "Existing venv found, refreshing..."
    rm -rf test/e2e/.venv
fi

echo "Creating Python venv..."
python3 -m venv test/e2e/.venv
source test/e2e/.venv/bin/activate

echo "Installing dependencies..."
pip install --quiet -r test/e2e/requirements.txt

# setuptools required for Python 3.13+
echo "Installing setuptools (required for Python 3.13+)..."
pip install --quiet setuptools

echo ""
echo "=== E2E environment ready ==="
echo "Activate with: source test/e2e/.venv/bin/activate"
echo "Run tests:     python -m pytest test/e2e/tests/test_<resource>.py -v"
echo ""
echo "Required env vars:"
echo "  export AWS_ACCOUNT_ID=<your-test-account>"
echo "  export AWS_REGION=<region>"
