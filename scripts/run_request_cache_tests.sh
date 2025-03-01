#!/bin/bash

# Run Request Cache Tests
# This script runs the unit tests for the request-level caching functionality

echo "Running Request Cache Tests..."
echo "======================================"

# Change to project root directory
cd "$(dirname "$0")/.." || exit 1

# Activate virtual environment if available
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
elif [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
elif [ -d "raenv" ]; then
    echo "Activating virtual environment..."
    source raenv/bin/activate
fi

# Run the tests with coverage report
echo "Running tests with coverage..."
python -m coverage run -m unittest tests/test_request_cache.py
python -m coverage report -m --include="utils/request_cache.py"

# Run the tests directly
echo ""
echo "Running tests directly..."
./tests/test_request_cache.py

echo ""
echo "Tests completed!" 