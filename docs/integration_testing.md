# RepoAnalyzer Integration Testing Guide

This document provides instructions for running and extending the integration test suite for the RepoAnalyzer project.

## Overview

The integration test suite allows you to test multiple components of the RepoAnalyzer system working together. Unlike unit tests that test individual components in isolation, integration tests verify that different modules interact correctly with each other.

The test suite supports:

- Running tests for specific modules or all modules
- Generating coverage reports
- Producing detailed test summaries
- Generating JUnit XML reports for CI integration

## Running Integration Tests

### Basic Usage

To run all integration tests:

```bash
./scripts/run_integration_tests.py
```

This will discover and run all integration tests, and display a summary of the results.

### Running Tests for Specific Modules

To run integration tests for specific modules:

```bash
./scripts/run_integration_tests.py --modules indexer parser db
```

Available modules include:

- `indexer`: Repository indexing functionality
- `parser`: Code parsing and analysis
- `db`: Database interaction
- `ai`: AI-related functionality
- `utils`: Utility functions
- `semantic`: Semantic search and analysis

### Additional Options

The script supports several options to customize test execution:

```bash
./scripts/run_integration_tests.py --verbose --coverage --html-report --junit --fail-fast
```

- `--verbose`: Enable detailed test output
- `--coverage`: Generate a coverage report
- `--html-report`: Generate an HTML coverage report
- `--junit`: Generate a JUnit XML report for CI integration
- `--fail-fast`: Stop testing after the first failure
- `--output-dir DIR`: Specify a custom directory for test reports (default: `test_reports`)

## Test Report Output

All test reports are saved in the specified output directory (default: `test_reports`):

- `integration_test_summary_TIMESTAMP.json`: JSON format of test results
- `integration_test_summary_TIMESTAMP.txt`: Human-readable summary
- `coverage.xml`: XML coverage report (if `--coverage` is specified)
- `coverage_html/`: HTML coverage report (if `--html-report` is specified)
- `junit.xml`: JUnit XML report (if `--junit` is specified)

## Creating Integration Tests

### Naming Convention

Integration tests should follow these naming conventions:

- Files should be named `test_integration_*.py` to be discovered by the test runner
- Module-specific tests should include the module name in the filename, e.g., `test_integration_indexer_*.py`

### Test Structure

Integration tests should focus on testing interactions between multiple components. Example structure:

```python
import pytest
from repoanalyzer import indexer, parser, db

def test_indexer_parser_integration():
    # Test indexer and parser working together
    sample_file = "sample_code.py"
    indexed_result = indexer.index_file(sample_file)
    parsed_result = parser.parse_indexed_file(indexed_result)
    
    # Assert expectations about the integration
    assert parsed_result.contains_valid_ast
    assert len(parsed_result.features) > 0
```

### Test Fixtures

Use pytest fixtures to set up test environments that are reused across tests:

```python
@pytest.fixture
def sample_repository():
    # Create a temporary repository
    repo_path = setup_temp_repository()
    yield repo_path
    # Clean up
    tear_down_repository(repo_path)

def test_full_indexing_flow(sample_repository):
    # Use the fixture
    result = indexer.index_repository(sample_repository)
    # Test assertions
    assert result.success
```

## Continuous Integration

The integration test suite is designed to work well with CI systems. Here's an example of how to use it in a GitHub Actions workflow:

```yaml
name: Integration Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  integration-tests:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v2
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
        pip install pytest pytest-cov
    - name: Run integration tests
      run: |
        ./scripts/run_integration_tests.py --coverage --junit
    - name: Upload test results
      uses: actions/upload-artifact@v2
      with:
        name: test-results
        path: test_reports/
```

## Best Practices

1. **Focus on Interactions**: Integration tests should focus on how components interact, not on internal details.
2. **Keep Tests Independent**: Each test should be self-contained and not depend on the state from other tests.
3. **Use Real Dependencies**: When possible, use real dependencies (e.g., test databases) rather than mocks.
4. **Test Realistic Scenarios**: Design tests to cover realistic user scenarios and workflows.
5. **Balance Coverage and Speed**: Integration tests are typically slower than unit tests, so focus on critical paths.

## Troubleshooting

### Common Issues

- **Test Discovery Failure**: Ensure test files follow the naming convention (`test_integration_*.py`).
- **Module Assignment Issues**: If tests aren't being associated with the correct module, check the file path and name.
- **Dependency Issues**: Ensure all required dependencies are installed.

### Debug Mode

For more detailed logging during test execution, use the `--verbose` flag:

```bash
./scripts/run_integration_tests.py --verbose
```

This will display additional information about test discovery and execution.

## Extending the Test Suite

To add support for testing new modules:

1. Update the `discover_test_modules()` function in `run_integration_tests.py` to include the new module.
2. Create integration test files following the naming convention.
3. Ensure the test files contain appropriate test functions using pytest.

## Getting Help

If you encounter issues with the integration test suite, please:

1. Check this documentation for guidance
2. Look at existing integration tests for examples
3. File an issue in the project repository with details about the problem
