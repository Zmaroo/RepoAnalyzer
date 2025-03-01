# Tree-sitter Block Extraction

This document describes the Tree-sitter Block Extraction feature in RepoAnalyzer, which provides more accurate and language-aware extraction of code blocks from source files.

## Overview

The Tree-sitter Block Extraction feature replaces the previous heuristic-based approach for extracting code blocks with a more precise method that leverages tree-sitter's Abstract Syntax Tree (AST) capabilities. This improvement enhances the accuracy of extracted code blocks, handles complex nested structures correctly, and provides consistent behavior across different programming languages.

## Key Improvements

Compared to the previous heuristic-based approach, Tree-sitter Block Extraction offers several benefits:

1. **Language-aware extraction**: Uses tree-sitter's language-specific knowledge to correctly identify and extract blocks according to the language's syntax rules
2. **Precise boundary detection**: Extracts blocks with exact boundaries using AST node information instead of string-based heuristics
3. **Proper handling of nested structures**: Correctly handles blocks that contain other blocks, complex expressions, or multi-line statements
4. **Better extraction of language-specific constructs**: Accurately extracts blocks for language-specific syntax like Python's indentation-based blocks vs. C++'s brace-based blocks
5. **Direct node text access**: Gets the exact text for a node directly from the AST, avoiding string manipulation or position-based extraction errors

## Architecture

The implementation consists of several key components:

1. **TreeSitterBlockExtractor class**: Core utility for extracting blocks from various types of tree-sitter nodes
2. **ExtractedBlock dataclass**: Standardized representation of extracted blocks with metadata
3. **Integration with pattern processor**: Updated pattern processing to use tree-sitter block extraction when available
4. **Language-specific handling**: Special handling for language-specific node types and structures
5. **Fallback mechanism**: Graceful fallback to the heuristic approach when tree-sitter extraction fails or is unavailable

## Usage

The block extractor is used automatically by the pattern processor and tree-sitter parser. You don't need to call it directly in most cases, but it's available for use in custom parsers or extensions.

### Direct Usage

If you need to use the block extractor directly:

```python
from parsers.block_extractor import block_extractor

# Extract a block from a node
block = block_extractor.extract_block(
    language_id="python",
    source_code=source_code,
    node_or_match=node  # Can be a tree-sitter Node, PatternMatch, or query result
)

if block:
    # Access extracted content and metadata
    content = block.content
    start_point = block.start_point
    end_point = block.end_point
    node_type = block.node_type
```

### Extracting Child Blocks

To extract all block-like children from a parent node:

```python
blocks = block_extractor.get_child_blocks(
    language_id="python",
    source_code=source_code,
    parent_node=root_node
)

for block in blocks:
    # Process each child block
    print(f"Found {block.node_type} block: {block.content[:50]}...")
```

## Language Support

Tree-sitter Block Extraction supports all languages with tree-sitter parsers in the RepoAnalyzer project. It has enhanced support for:

- Python
- JavaScript/TypeScript
- C/C++
- Java
- Go
- Rust

For other languages, it provides generic block extraction capabilities with reasonable defaults.

## Fallback Mechanism

The system automatically falls back to the previous heuristic-based approach when:

1. Tree-sitter parsing fails for any reason
2. The language doesn't have tree-sitter support
3. The specific block cannot be correctly identified by tree-sitter

This ensures backward compatibility and graceful degradation when tree-sitter extraction isn't possible.

## Implementation Details

### Block Node Types

The extractor recognizes common block node types across languages:

- `block`, `compound_statement`, `statement_block`
- `function_body`, `class_body`, `method_body`

It also handles language-specific block types like:

- Python: `function_definition`, `class_definition`, `if_statement`, etc.
- JavaScript: `function_declaration`, `method_definition`, `class_declaration`, etc.
- C++: `compound_statement`, `function_definition`, `class_specifier`, etc.

### Container Node Types

For recursive traversal, the extractor identifies container node types:

- Common types: `program`, `source_file`, `translation_unit`, etc.
- Language-specific containers: module, namespace, class, etc.

### Block Extraction Process

The extraction process follows these steps:

1. Determine if tree-sitter extraction is available for the language
2. Parse the source code to get the AST
3. Find the appropriate node for extraction (by position, query result, etc.)
4. Extract the block content directly from the node
5. Handle language-specific edge cases
6. Fall back to heuristic extraction if needed

## Performance Considerations

Tree-sitter Block Extraction may have a small performance cost compared to the heuristic approach, but the benefits in accuracy significantly outweigh this cost. The implementation includes:

1. **Caching integration**: Works with the existing AST caching system
2. **Error handling**: Robust error handling with graceful fallbacks
3. **Resource management**: Careful management of tree-sitter resources

## Future Improvements

Potential future improvements to Tree-sitter Block Extraction include:

1. **More language-specific handlers**: Adding specialized handling for additional languages
2. **Performance optimizations**: Further optimizing the extraction process
3. **Block transformation capabilities**: Adding capabilities to transform or normalize extracted blocks
4. **Block validation**: Validating that extracted blocks are syntactically correct
5. **Improved annotation**: Adding more detailed metadata to extracted blocks
