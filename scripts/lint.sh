#!/bin/bash
# Run linters (Black and Ruff)
# Usage: ./scripts/lint.sh [--fix]

set -e

FIX_MODE=false
if [ "$1" == "--fix" ]; then
    FIX_MODE=true
fi

echo "🔍 Running linters for CK Coding Lab..."
echo "========================================"

# Check if black is installed
if ! command -v black &> /dev/null; then
    echo "❌ Black not found. Installing..."
    pip install black
fi

# Check if ruff is installed
if ! command -v ruff &> /dev/null; then
    echo "❌ Ruff not found. Installing..."
    pip install ruff
fi

echo ""
echo "🎨 Running Black formatter..."
if [ "$FIX_MODE" = true ]; then
    black --line-length=100 .
    echo "✅ Black formatting applied!"
else
    black --line-length=100 --check --diff .
    echo "✅ Black check passed!"
fi

echo ""
echo "⚡ Running Ruff linter..."
if [ "$FIX_MODE" = true ]; then
    ruff check --fix .
    echo "✅ Ruff fixes applied!"
else
    ruff check .
    echo "✅ Ruff check passed!"
fi

echo ""
echo "🎯 All linting checks complete!"
if [ "$FIX_MODE" = false ]; then
    echo "   Run './scripts/lint.sh --fix' to auto-fix issues"
fi
