# RepoAnalyzer Testing Guide

This document provides instructions on how to test the RepoAnalyzer system to ensure it's working correctly.

## Prerequisites

Before you can test the system, make sure you have all the required dependencies:

```bash
pip install -r requirements.txt
```

The system requires:

- Python 3.8+
- Neo4j database (for graph operations)
- PostgreSQL (for relational data storage)
- Redis (for caching)
- Tree-sitter language pack

## Basic Testing

### Enhanced System Test

To verify the full functionality of the system with data verification, run:

```bash
python test_system.py
```

This will:

1. Test the system by running `python index.py --index` as a subprocess
2. Test the system by calling the main API directly
3. Verify that data was correctly stored in PostgreSQL and Neo4j
4. Check that the language detection is working properly

Options:

```bash
# Run only the subprocess test
python test_system.py --subprocess-only

# Run only the API test with verification
python test_system.py --api-only

# Skip detailed verification (faster)
python test_system.py --skip-verification
```

### Comprehensive Pipeline Test

For in-depth testing of each component of the pipeline, use:

```bash
python test_pipeline.py
```

This script tests each stage of the pipeline in isolation:

1. Language detection from filenames and content
2. Parser selection logic
3. AST generation and code feature extraction
4. Database operations (PostgreSQL and Neo4j)
5. Graph projection functionality
6. Semantic search capabilities

Options:

```bash
# Clean databases before testing
python test_pipeline.py --clean

# Use a different repository path
python test_pipeline.py --repo-path /path/to/repository
```

### Testing Reference Repository Functionality

To test the reference repository functionality (cloning, learning patterns, and applying them):

```bash
python test_reference_repo.py
```

By default, it uses the Python 'requests' library repository as a reference. You can specify a different reference repository:

```bash
python test_reference_repo.py --ref-repo https://github.com/username/repo.git
```

Options:

- `--subprocess-only`: Only run the subprocess tests, not the API tests
- `--api-only`: Only run the API tests, not the subprocess tests
- `--skip-clone`: Skip cloning step (assume repo already cloned)
- `--skip-learn`: Skip learning patterns step
- `--skip-apply`: Skip applying patterns step

## Step-by-Step Manual Testing

If you prefer to test the system manually, follow these steps:

### 1. Basic Indexing

```bash
python index.py --index
```

This will index the current directory.

### 2. Clone and Index a Reference Repository

```bash
python index.py --clone-ref https://github.com/psf/requests.git
```

### 3. Learn Patterns from Reference Repository

```bash
python index.py --learn-ref https://github.com/psf/requests.git
```

### 4. Apply Learned Patterns

```bash
python index.py --apply-ref-patterns
```

### 5. Watch Mode

If you want to test the watch mode (continuous indexing on file changes):

```bash
python index.py --watch
```

## Understanding the Pipeline

The RepoAnalyzer pipeline for `python index.py --index` consists of these key stages:

1. **Argument Parsing & Setup**: Processes command line arguments and initializes components.

2. **File Discovery**: Scans the repository to find all processable files.

3. **Language Detection**: Determines the programming language of each file using:
   - File extension matching
   - Content-based detection
   - Filename patterns

4. **Parsing**: Uses the appropriate parser for each language to:
   - Generate Abstract Syntax Trees (ASTs)
   - Extract code blocks, functions, classes, etc.
   - Calculate complexity metrics
   - Identify dependencies and imports

5. **Data Storage**:
   - Stores code snippets and metadata in PostgreSQL
   - Creates a graph representation in Neo4j

6. **Graph Analysis**:
   - Generates graph projections for analytics
   - Analyzes code structure and relationships

7. **Search & AI Capabilities**:
   - Creates embeddings for semantic search
   - Enables pattern learning from reference repositories

This pipeline ensures that code is properly analyzed, stored, and made available for search and understanding.

## Troubleshooting

### Database Issues

If you encounter database issues:

1. Reset the databases:

   ```bash
   python index.py --clean
   ```

2. Check Neo4j and PostgreSQL connection settings.

### Parser Issues

If there are issues with specific language parsers:

1. Check that tree-sitter language pack is installed
2. Verify that the language is supported in `parsers/language_mapping.py`
3. Use the pipeline test to identify specific parser failures:

   ```bash
   python test_pipeline.py
   ```

### Log Files

Check the log files in the `logs/` directory for detailed error information.

## Running Integration Tests

For more comprehensive testing, run the integration test suite:

```bash
pytest tests/test_integration_indexer.py
```

Or run all tests:

```bash
pytest
```

## Running Tests with Coverage

To run tests with coverage analysis to see how much of the codebase is being tested, use:

```bash
python run_tests_with_coverage.py --html
```

This will run all tests and generate a coverage report showing which lines of code are covered by tests and which are not.

Options:

- `--html`: Generate HTML coverage report (view at `test_reports/htmlcov/index.html`)
- `--xml`: Generate XML coverage report (useful for CI systems)
- `--specific path/to/test.py`: Run coverage on specific test files only
- `--omit pattern1,pattern2`: Specify patterns to exclude from coverage

### Understanding Coverage Reports

The coverage report shows:

1. **Line coverage**: Percentage of code lines that are executed during tests
2. **Missing lines**: Specific lines that aren't being tested
3. **Branch coverage**: Whether conditional branches (if/else) are fully tested

A high coverage percentage (80%+) indicates well-tested code. Areas with low coverage may need additional tests.

### Improving Coverage

If you find areas with low coverage:

1. Add specific tests for those modules/functions
2. Include edge cases in your tests
3. Focus on critical code paths first

## Test Coverage Improvement Strategy

Based on our coverage analysis (22% overall), here's a systematic approach to improve test coverage:

1. **Core Parser Components (Priority: High)**
   - Implement tests for `parsers/tree_sitter_parser.py` (currently 16% coverage)
   - Add tests for `parsers/base_parser.py` focusing on lines 45-149
   - Create additional tests for `parsers/block_extractor.py` (22% coverage)

2. **Language-Specific Parsers (Priority: Medium)**
   - Create a test factory to generate tests for all language-specific parsers
   - Focus on the most commonly used languages first:
     - JavaScript/TypeScript
     - Python
     - HTML/XML
     - Markdown
   - Implement parameterized tests with sample code snippets for each language

3. **Feature Extraction (Priority: High)**
   - Add tests for `parsers/feature_extractor.py` (15% coverage)
   - Test different feature categories and extraction methods

4. **Pattern Processing (Priority: Medium)**
   - Enhance tests for `parsers/pattern_processor.py` (16% coverage)
   - Test pattern matching across different languages

5. **Database Operations (Priority: High)**
   - Improve mock DB testing to ensure DB operations are well covered
   - Add integration tests for PostgreSQL and Neo4j operations

6. **AI Tools (Priority: Medium)**
   - Add tests for `ai_tools/reference_repository_learning.py` (16% coverage)
   - Create tests for `ai_tools/rule_config.py` (0% coverage)

7. **Embedding and Semantic Search (Priority: Medium)**
   - Implement tests for embedding models and vector operations
   - Test semantic search functionality with mock embeddings

8. **Test Utilities**
   - Create helper functions and fixtures to simplify test creation
   - Implement tools for generating test data across languages

## Test Implementation Plan

1. **Short-term (1-2 weeks):**
   - Focus on items #1 and #3 to improve core parser and feature extraction coverage
   - Fix broken tests in the existing test suite
   - Implement basic test factories for language-specific parsers

2. **Medium-term (2-4 weeks):**
   - Address items #2, #4, and #5
   - Implement comprehensive test suites for pattern processing and DB operations
   - Add missing tests for all supported languages

3. **Long-term (4+ weeks):**
   - Complete items #6 and #7
   - Implement end-to-end tests for the entire pipeline
   - Achieve >75% test coverage across all modules

## Test Execution

Run specific coverage tests with:

```bash
# Test core parser components
./run_direct_coverage.py --html --specific tests/test_parser_unit.py

# Test feature extraction
./run_direct_coverage.py --html --specific tests/test_feature_extractor.py

# Test full system with subprocess
./run_direct_coverage.py --html --script=test_system.py --args="--subprocess-only"
```

View HTML coverage reports at `test_reports/htmlcov/index.html`

## Getting Help

If you encounter issues that aren't resolved by these testing procedures, check:

1. The documentation in the `docs/` directory
2. The examples in the `examples/` directory
3. Any error messages in the console or log files
