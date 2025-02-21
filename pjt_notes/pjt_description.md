# Code Analysis and Documentation Framework

A comprehensive framework for parsing, analyzing, and documenting source code across multiple programming languages and documentation formats. The system uses a combination of tree-sitter parsers and custom parsers to extract structured information from source files.

## Core Components

### Parser System

- **Tree-sitter Integration**: Native support for popular programming languages through tree-sitter
- **Custom Parsers**: Specialized parsers for documentation formats and configuration files
- **Unified Interface**: Common parsing interface across all supported formats

### Feature Categories

1. **Syntax**: Language-specific constructs (functions, classes, types)
2. **Structure**: Code organization (modules, imports, namespaces)
3. **Documentation**: Comments, annotations, and documentation blocks
4. **Semantics**: Variables, expressions, and type information

### Pattern System

- Standardized query patterns for each supported language
- Category-based pattern organization
- Extensible pattern matching for both tree-sitter and custom parsers

### File Classification

- Automatic detection of file types and appropriate parsers
- Support for both code and documentation files
- Configuration-based file type mapping

## Supported Formats

### Programming Languages

- Tree-sitter supported languages (Python, JavaScript, Java, etc.)
- Custom parser support (OCaml, Cobalt)

### Documentation

- Markdown
- reStructuredText
- AsciiDoc
- Plain text

### Configuration

- YAML
- TOML
- INI
- EditorConfig

## Usage

The framework provides a unified interface for parsing and analyzing source code:

1. File classification determines the appropriate parser
2. Parser extracts AST and features based on standardized patterns
3. Features are categorized into syntax, structure, documentation, and semantics
4. Results can be used for documentation generation, code analysis, or IDE integration

## Extension

The system is designed for easy extension through:

- Adding new tree-sitter language support
- Creating custom parsers for new formats
- Defining additional query patterns
- Extending feature categories

## Integration

Can be integrated with:

- Documentation generators
- Code analysis tools
- IDE plugins
- CI/CD pipelines
