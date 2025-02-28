# Language Support in RepoAnalyzer

This document outlines the language support capabilities in the RepoAnalyzer system, including supported languages, detection mechanisms, and parser types.

## Supported Languages

RepoAnalyzer supports a wide range of programming languages through both Tree-sitter parsers and custom parsers. Here's a breakdown of the current support:

### Tree-sitter Languages

These languages use Tree-sitter for precise syntax-aware parsing:

- Python
- JavaScript/TypeScript
- Java
- C/C++
- Go
- Ruby
- Rust
- PHP
- Kotlin
- Swift
- Scala
- Shell/Bash
- HTML
- CSS
- JSON
- YAML
- And many more...

### Custom Parser Languages

For languages or file types without Tree-sitter support, we use custom parsers:

- Markdown
- ReStructuredText
- AsciiDoc
- Environment files (.env)
- EditorConfig
- Configuration files
- GraphQL
- Plaintext

## Language Detection Process

The system uses a multi-stage approach to identify the correct language for each file:

1. **Filename-based detection**:
   - First, checks for exact filename matches (e.g., "Dockerfile", "Makefile")
   - Then checks file extensions against known mappings
   - Finally checks for special patterns (e.g., ".config.js")

2. **Content-based detection** (if filename detection is inconclusive):
   - Looks for shebang lines (#!) at the beginning of the file
   - Searches for language-specific markers and patterns
   - Analyzes content structure to infer language

3. **Fallback mechanisms**:
   - If no language is detected, defaults to "plaintext"
   - For parsing failures, can try alternative language suggestions

## Parser Selection Process

The process for selecting a parser for a specific file:

1. **Parser Type Determination**:
   - Based on the language, determines the appropriate parser type
   - Prefers Tree-sitter parsers where available for accurate AST-based parsing
   - Falls back to custom parsers for specialized formats

2. **Fallback Parsers**:
   - If a primary parser fails, automatically tries fallback parser types
   - For example, can fall back from Tree-sitter to custom parsers for HTML/XML

3. **Language Alternatives**:
   - If parsing fails with the detected language, can try similar languages
   - For example, can try JavaScript as a fallback for TypeScript

## Language Features

For each supported language, the system provides:

- File extension mappings
- MIME type associations
- Parser type information
- Specialized patterns for feature extraction
- File type categorization (code, documentation, configuration, or data)

## Language Mapping Customization

The language mapping system is designed to be easily extensible:

- New language support can be added by updating the mapping definitions
- Custom parsers can be registered for specialized language handling
- Additional file extensions can be associated with existing languages

## Implementation Details

The language support system is implemented across several modules:

- `parsers/language_mapping.py`: Central definition of language mappings and utilities
- `parsers/file_classification.py`: File classification based on path and content
- `parsers/language_support.py`: Parser registry and language feature management
- `parsers/unified_parser.py`: Unified interface for parsing different languages

## Binary File Handling

The system also includes robust binary file detection:

- Uses file extensions to quickly identify common binary formats
- Leverages libmagic (when available) for more accurate content-based detection
- Properly handles binary files by avoiding text processing operations
