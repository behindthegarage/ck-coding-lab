#!/bin/bash
# Run tests with coverage report
# Usage: ./scripts/test-coverage.sh

set -e

echo "📊 Running CK Coding Lab tests with coverage..."
echo "================================================"

# Set test environment
export SECRET_KEY=test-secret-key
export FLASK_ENV=testing
export CKCL_DB_PATH=:memory:

# Run pytest with coverage
echo ""
echo "📈 Generating coverage report..."
pytest --cov=app \
       --cov=auth \
       --cov=database \
       --cov=sandbox \
       --cov=admin_routes \
       --cov=file_routes \
       --cov=chat \
       --cov=ai \
       --cov-report=term-missing \
       --cov-report=html \
       --cov-report=xml \
       --cov-fail-under=80 \
       -v

echo ""
echo "✅ Coverage report generated!"
echo ""
echo "📁 HTML report: htmlcov/index.html"
echo "📄 XML report: coverage.xml"
