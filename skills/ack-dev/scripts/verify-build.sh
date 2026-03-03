#!/usr/bin/env bash
# Verify a controller build produced all expected generated files.
# Run from the service controller directory after build-controller.sh.
# Usage: verify-build.sh

set -euo pipefail

ERRORS=0

echo "=== Verifying build output ==="

# Check go build compiles
echo -n "Compiling controller... "
if go build -o bin/controller ./cmd/controller 2>/dev/null; then
    echo "OK"
else
    echo "FAIL"
    ERRORS=$((ERRORS + 1))
fi

# Check expected generated directories have changes
echo ""
echo "=== Changed files by area ==="
for dir in apis/v1alpha1 pkg/resource config/crd config/rbac helm; do
    count=$(git diff --name-only -- "$dir" 2>/dev/null | wc -l | tr -d ' ')
    staged=$(git diff --cached --name-only -- "$dir" 2>/dev/null | wc -l | tr -d ' ')
    untracked=$(git ls-files --others --exclude-standard -- "$dir" 2>/dev/null | wc -l | tr -d ' ')
    total=$((count + staged + untracked))
    if [[ $total -gt 0 ]]; then
        echo "  $dir: $total file(s) changed"
    else
        echo "  $dir: no changes"
    fi
done

# Helm chart check
echo ""
echo -n "Helm chart updated... "
helm_changes=$(git diff --name-only -- helm/ 2>/dev/null | wc -l | tr -d ' ')
helm_staged=$(git diff --cached --name-only -- helm/ 2>/dev/null | wc -l | tr -d ' ')
helm_untracked=$(git ls-files --others --exclude-standard -- helm/ 2>/dev/null | wc -l | tr -d ' ')
if [[ $((helm_changes + helm_staged + helm_untracked)) -gt 0 ]]; then
    echo "YES"
else
    echo "WARNING: No Helm changes detected. This is a common miss."
    ERRORS=$((ERRORS + 1))
fi

# Summary
echo ""
if [[ $ERRORS -eq 0 ]]; then
    echo "=== All checks passed ==="
else
    echo "=== $ERRORS issue(s) found ==="
fi

exit $ERRORS
