#!/bin/bash

# Run Pattern Statistics Tests
# This script runs the unit tests for the pattern statistics functionality

echo "Running Pattern Statistics Tests..."
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
python -m coverage run -m unittest tests/test_pattern_statistics.py
python -m coverage report -m --include="analytics/pattern_statistics.py"

# Run the tests directly
echo ""
echo "Running tests directly..."
./tests/test_pattern_statistics.py

echo ""
echo "Tests completed!" 