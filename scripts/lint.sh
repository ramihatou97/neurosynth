#!/bin/bash
set -e

echo "Running Black..."
black src/ tests/

echo "Running Ruff..."
ruff check src/ tests/ --fix

echo "Linting complete!"
