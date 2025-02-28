# RepoAnalyzer

A robust code analysis tool for extracting patterns, understanding code structures, and analyzing repositories at scale.

## Features

- **Repository Analysis**: Automatically analyze codebases to extract patterns and structures
- **Language Support**: Comprehensive support for multiple programming languages
- **Graph Database Integration**: Store code relationships in Neo4j for advanced querying
- **Pattern Detection**: Identify code patterns, anti-patterns, and architectural structures
- **Machine Learning Capabilities**: Learn from repositories to improve pattern detection
- **Robust Error Handling**: Comprehensive exception management with retry capabilities
- **Extensible Architecture**: Easy to extend with new languages and patterns

## Getting Started

### Prerequisites

- Python 3.8+
- Neo4j 4.4+
- PostgreSQL 13+

### Installation

1. Clone the repository

   ```bash
   git clone https://github.com/your-org/RepoAnalyzer.git
   cd RepoAnalyzer
   ```

2. Install dependencies

   ```bash
   pip install -r requirements.txt
   ```

3. Configure database connections

   ```bash
   # Create configuration file from template
   cp config/config.example.json config/config.json
   # Edit config.json with your database credentials
   ```

### Basic Usage

Analyze a Git repository:

```bash
python index.py --repo https://github.com/example/repository.git
```

Process a local codebase:

```bash
python index.py --path /path/to/codebase
```

## Architecture

RepoAnalyzer is built with a modular architecture:

- **Parsers**: Language-specific code parsing and pattern extraction
- **Indexer**: Core analysis engine that processes code files
- **Database**: Storage layer with Neo4j for graph relationships and PostgreSQL for metadata
- **AI Tools**: ML-enhanced capabilities for pattern learning and recognition

## Reliability Features

### Exception Handling System

RepoAnalyzer implements a comprehensive exception handling framework:

- **Standardized Error Types**: Hierarchical exception classes for different error categories
- **Decorated Error Boundaries**: Use of decorators and context managers for consistent error handling
- **Retry Mechanism**: Automatic retry with exponential backoff for transient failures
- **Error Auditing**: Tools to analyze exception patterns and improve error handling

To run the exception handling audit:

```bash
./scripts/analyze_exception_patterns.py --verbose
```

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run specific test modules
pytest tests/test_parsers.py
```

### Documentation

Comprehensive documentation is available in the `docs/` directory:

- [Exception Handling Guide](docs/exception_handling_guide.md)
- [Component-Specific Error Handling](docs/component_error_handling.md)
- [Language Support Documentation](docs/language_support.md)

## Roadmap

See the [improvement roadmap](pjt_notes/improvement_roadmap.md) for planned enhancements and current priorities.

## Contributing

Contributions are welcome! Please check the [contributing guidelines](CONTRIBUTING.md) before submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
