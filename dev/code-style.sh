#!/bin/bash
# Auto-fix linting and formatting issues (default behavior)
# Use --check flag to only check without fixing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

CHECK_ONLY=false

# Check if --check flag is provided
if [[ "$1" == "--check" ]]; then
    CHECK_ONLY=true
    shift
fi

if [ "$CHECK_ONLY" = true ]; then
    echo "Running ruff check..."
    uv run ruff check .
    
    echo "Running ruff format check..."
    uv run ruff format --check .
    
    echo "All linting and formatting checks passed!"
else
    echo "Auto-fixing linting issues..."
    uv run ruff check . --fix
    
    echo "Auto-formatting code..."
    uv run ruff format .
    
    echo "Code formatted and linting issues fixed!"
fi
