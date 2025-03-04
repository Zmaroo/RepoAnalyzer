# Parser Flow Documentation

## Overview

The parser system provides a unified interface for analyzing source code using both tree-sitter and custom parsers. The system is designed to be modular, extensible, and asynchronous, with comprehensive error handling and resource management.

## Core Components

1. **Unified Parser** (`unified_parser.py`)
   - Entry point for all parsing operations
   - Coordinates between different components
   - Manages parser lifecycle and resource cleanup
   - Provides configurable parsing options

2. **File Classification** (`file_classification.py`)
   - Determines file type and appropriate parser
   - Uses MIME types and content analysis
   - Calculates confidence scores for classifications
   - Handles binary file detection

3. **Language Support** (`language_support.py`)
   - Manages tree-sitter grammar loading
   - Caches language parsers
   - Provides dynamic parser selection
   - Handles parser initialization and cleanup

4. **Feature Extraction** (`feature_extractor.py`)
   - Extracts code features using tree-sitter queries
   - Supports multiple feature categories:
     - Syntax (functions, classes, etc.)
     - Semantics (types, references)
     - Documentation (docstrings, comments)
   - Provides unified feature extraction interface

5. **Block Extraction** (`block_extractor.py`)
   - Extracts code blocks from AST
   - Supports various block types:
     - Functions
     - Classes
     - Control flow structures
   - Maintains block hierarchy and relationships

## Parser Pipelines

### Tree-Sitter Pipeline

1. **Initialization**

   ```text
   File -> FileClassifier -> TreeSitterParser -> LanguageLoading
   ```

2. **Parsing Process**

   ```text
   SourceCode -> ASTGeneration -> NodeTraversal -> FeatureExtraction
   ```

3. **Feature Extraction**

   ```text
   AST -> QueryExecution -> FeatureCollection -> ResultAssembly
   ```

4. **Block Extraction**

   ```text
   AST -> BlockIdentification -> HierarchyBuilding -> BlockCollection
   ```

### Custom Parser Pipeline

1. **Initialization**

   ```text
   File -> FileClassifier -> CustomParser -> ParserLoading
   ```

2. **Parsing Process**

   ```text
   SourceCode -> CustomParsing -> InternalRepresentation -> FeatureExtraction
   ```

3. **Feature Extraction**

   ```text
   ParsedData -> PatternMatching -> FeatureCollection -> ResultAssembly
   ```

4. **Block Extraction**

   ```text
   ParsedData -> BlockRecognition -> StructureAnalysis -> BlockCollection
   ```

## Detailed Flow

1. **File Input**
   - File is provided to UnifiedParser
   - ParsingOptions specify extraction requirements

2. **Classification**
   - FileClassifier analyzes file content and extension
   - Determines appropriate parser type
   - Calculates confidence score

3. **Parser Selection**
   - For tree-sitter supported languages:
     - Loads appropriate grammar
     - Initializes TreeSitterParser
   - For other languages:
     - Loads appropriate custom parser
     - Initializes parser with language-specific settings

4. **Parsing**
   - Tree-sitter:
     - Generates AST
     - Executes predefined queries
     - Extracts node information
   - Custom:
     - Uses language-specific parsing logic
     - Generates internal representation
     - Maps to common feature model

5. **Feature Extraction**
   - Common features:
     - Functions and methods
     - Classes and types
     - Imports and dependencies
   - Language-specific features:
     - Special syntax constructs
     - Framework-specific patterns
     - Custom annotations

6. **Block Extraction**
   - Identifies code blocks
   - Establishes parent-child relationships
   - Extracts block content and metadata
   - Maintains source location information

7. **Result Assembly**
   - Combines all extracted information
   - Formats according to ParserResult structure
   - Includes parsing statistics and metadata

## Error Handling

- Comprehensive error boundaries at each stage
- Graceful degradation for partial failures
- Detailed error logging and reporting
- Resource cleanup on failures

## Resource Management

- Automatic parser cleanup
- Language grammar caching
- Memory-efficient processing
- Asynchronous operation support

## Performance Considerations

1. **Caching**
   - Parser instances are cached
   - Language grammars are cached
   - Feature extraction patterns are compiled once

2. **Lazy Loading**
   - Parsers are initialized on demand
   - Resources are loaded when needed
   - Cleanup occurs automatically

3. **Parallel Processing**
   - Asynchronous parsing support
   - Concurrent feature extraction
   - Independent block processing

## Extension Points

1. **Custom Parsers**
   - Implement BaseParser interface
   - Register in CUSTOM_PARSER_CLASSES
   - Provide language-specific features

2. **Feature Extractors**
   - Add new feature categories
   - Implement custom extractors
   - Extend pattern matching

3. **Block Extractors**
   - Support new block types
   - Implement custom block recognition
   - Add specialized metadata

## Usage Example

```python
# Initialize parser
parser = UnifiedParser()

# Configure options
options = ParsingOptions(
    extract_features=True,
    extract_blocks=True,
    include_ast=False
)

# Parse file
result = await parser.parse_file(
    file_path="example.py",
    content=source_code,
    options=options
)

# Access results
if result and result.success:
    features = result.features
    blocks = result.blocks
    documentation = result.documentation
```
