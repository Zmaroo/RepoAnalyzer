# Parser Flow

## Detailed Flow

### 1. Entry Point [parsers/unified_parser.py]

- Input: file_path (str), content (str)
- Cache check: f"parse:{file_path}:{hash(content)}"
- Returns: Optional[ParserResult]

### 2. Language Detection [parsers/language_support.py]

- Uses file extension to determine language
- Normalizes language name
- Determines parser type (Tree-sitter vs Custom)
- Returns: LanguageFeatures

### 3. Parser Selection [parsers/language_registry.py]

- Gets appropriate parser instance
- Initializes parser if needed
- Returns: BaseParser implementation

### 4. Feature Extraction [parsers/feature_extractor.py]

#### Tree-sitter Path

- Uses tree-sitter queries from query_patterns/
- Processes AST for features
- Example (Python):

  ```python
  "pattern": """
      (function_definition
          name: (identifier) @syntax.function.name
          parameters: (parameters) @syntax.function.params
  """
  ```

#### Custom Parser Path

- Uses regex patterns
- Direct text analysis
- Returns: ExtractedFeatures

### 5. Pattern Processing [parsers/pattern_processor.py]

- Processes matches from either parser type
- Extracts relevant information
- Example:

  ```python
  "extract": lambda node: {
      "module": node["captures"].get("structure.import.module", {}).get("text", ""),
      "name": node["captures"].get("structure.import.from.name", {}).get("text", "")
  }
  ```

### 6. Final Result

- Combines all extracted information
- Caches result
- Returns standardized ParserResult

## Key Files

- unified_parser.py: Main orchestration
- language_support.py: Language detection
- language_registry.py: Parser management
- feature_extractor.py: Feature extraction
- pattern_processor.py: Pattern handling
- query_patterns/: Language-specific patterns
