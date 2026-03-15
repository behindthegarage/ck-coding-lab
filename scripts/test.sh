#!/bin/bash
# Run all tests locally
# Usage: ./scripts/test.sh

set -e

echo "🧪 Running CK Coding Lab tests..."
echo "================================"

# Set test environment
export SECRET_KEY=test-secret-key
export FLASK_ENV=testing
export CKCL_DB_PATH=:memory:

# Run pytest with verbose output
echo ""
echo "📋 Running pytest..."
pytest -v --tb=short

echo ""
echo "✅ All tests passed!"
