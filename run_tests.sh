#!/bin/bash
#
# This script discovers and runs all unit tests for the stocksTUI application.
# It uses Python's built-in unittest module and the 'coverage' package.
# It will attempt to activate a virtual environment named 'venv'.
#
# Usage:
#   ./run_tests.sh
#
# To run without coverage:
#   ./run_tests.sh --no-coverage
#

# --- Script Start ---

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
else
    echo "Warning: No 'venv' directory found. Assuming dependencies are in the global scope."
fi

# Ensure dev dependencies are installed
pip install .[dev] > /dev/null 2>&1

# Check if coverage is installed
if ! python3 -m coverage --version > /dev/null 2>&1; then
    echo "Coverage.py is not installed. Please install it with 'pip install coverage'."
    echo "Running tests without coverage."
    exec python3 -m unittest discover -s tests -p 'test_*.py' -v
    exit $?
fi

# Check for --no-coverage flag
if [ "$1" == "--no-coverage" ]; then
    echo "Running stocksTUI unit tests without coverage..."
    exec python3 -m unittest discover -s tests -p 'test_*.py' -v
    exit $?
fi

echo "Running stocksTUI unit tests with coverage..."

# The 'coverage run -m' command executes the unittest module under coverage.
# We specify the source directory to get accurate reporting.
coverage run --source=stockstui -m unittest discover -s tests -p 'test_*.py' -v

# Check the exit code of the test command
TEST_EXIT_CODE=$?

if [ ${TEST_EXIT_CODE} -eq 0 ]; then
  echo "All tests passed successfully."
  echo "--- Coverage Report ---"
  # Generate a report in the terminal. --fail-under=80 will exit with an error
  # if coverage is below 80%.
  coverage report --fail-under=80
else
  echo "Some tests failed. Skipping coverage report."
fi

exit ${TEST_EXIT_CODE}
