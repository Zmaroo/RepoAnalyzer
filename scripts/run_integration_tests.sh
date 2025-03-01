#!/bin/bash
# Run integration tests for RepoAnalyzer
# This script sets up the Python environment and runs the integration tests

set -e  # Exit on error

# Change to the project root directory
cd "$(dirname "$0")/.."

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check for virtual environment
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Run the integration tests
python3 scripts/run_integration_tests.py "$@"

# Report success
exit_code=$?
if [ $exit_code -eq 0 ]; then
    echo "All integration tests completed successfully!"
else
    echo "Integration tests completed with errors."
fi

exit $exit_code 