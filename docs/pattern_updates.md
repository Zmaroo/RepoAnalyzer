# Pattern Extraction Updates for Reference Repository Learning

This document summarizes the updates made to the pattern extraction capabilities in the RepoAnalyzer tool.

## 1. Architecture Updates

### PATTERN_CATEGORIES Updates

- Added new `PatternType` enum in `parsers/models.py` to classify patterns:
  - `CODE_STRUCTURE`: For code organization patterns
  - `CODE_NAMING`: For variable and function naming conventions
  - `ERROR_HANDLING`: For exception handling patterns
  - `DOCUMENTATION_STRUCTURE`: For documentation organization
  - `ARCHITECTURE`: For project architecture patterns

- Added new `FeatureCategory.CODE_PATTERN` with subcategories for:
  - Code patterns (structure, naming, error handling, etc.)
  - Documentation patterns (structure, API docs, examples, etc.)
  - Configuration patterns (environment, dependencies, etc.)

### Base Parser Updates

- Added pattern extraction capabilities to `BaseParser` in `parsers/base_parser.py`:
  - Implemented a base `extract_patterns` method that all parsers inherit
  - Added code for using the pattern processor to extract language-specific patterns
  - Created specialized extraction methods for code and documentation patterns
  - Added error handling for pattern extraction operations

### Query Patterns Framework

- Created a framework in `parsers/query_patterns/__init__.py` to register repository learning patterns:
  - Added function to load and register patterns from all language modules
  - Created pattern categorization for repository learning
  - Added tracking of pattern registration for debugging purposes

- Updated `custom_parsers/__init__.py` to ensure all parsers support pattern extraction:
  - Added dynamic loading of all custom parser modules
  - Implemented a function to ensure all parsers have pattern extraction capability
  - Added a default pattern extraction implementation for parsers that don't have one

## 2. Core Components Updated

- **Query Patterns**: Enhanced to support repository learning patterns
- **Custom Parsers**: Updated with pattern extraction capabilities
- **Pattern Extraction API**: Standardized across parsers
- **Reference Repository Learning**: Improved integration with pattern extraction

## 3. Parser Updates

The following parsers have been updated with pattern extraction capabilities:

### Documentation Format Parsers

- **Markdown Parser**: Enhanced to detect and extract heading patterns, link patterns, and section structures
- **AsciiDoc Parser**: Added detection for AsciiDoc structure patterns, attribute usage, and cross-references
- **Cobalt Parser**: Added support for extracting component patterns and documentation structures
- **reStructuredText (RST) Parser**: Added extraction of section, directive, role, and reference patterns
- **Plaintext Parser**: Enhanced with text analysis, list detection, and writing style pattern extraction
- **XML Parser**: Added support for element patterns, attribute patterns, namespace patterns, and naming conventions

### Configuration Format Parsers

- **Editorconfig Parser**: Added detection for common editor settings and team conventions
- **Env Parser**: Enhanced to detect environment variable naming patterns and common configurations
- **INI Parser**: Added extraction of section patterns, property categories, and reference patterns
- **TOML Parser**: Enhanced to detect table structures, key-value patterns, array patterns, and naming conventions
- **YAML Parser**: Added extraction of mapping patterns, sequence patterns, anchors, aliases, and naming conventions

### GraphQL Parser

- **Type Definitions**: Detection of GraphQL schema type patterns
- **Query Structure**: Analysis of query, mutation, and subscription patterns
- **Naming Conventions**: Detection of naming conventions for types, fields, and arguments

### HTML Parser

- **Semantic Elements**: Detection of semantic HTML structure patterns (article, section, nav, etc.)
- **Component Patterns**: Identification of common components like navigation, forms, and cards
- **Accessibility**: Analysis of ARIA attributes and accessibility patterns
- **Data Attributes**: Extraction of custom data attribute patterns
- **Naming Conventions**: Detection of ID and class naming conventions (kebab-case, camelCase, etc.)
- **Embedded Content**: Analysis of embedded script and style patterns

### JSON Parser

- **Structure Patterns**: Detection of common JSON structures (configuration, API responses, collections)
- **Schema Detection**: Identification of JSON Schema patterns and property types
- **Field Patterns**: Analysis of common field patterns (IDs, timestamps, status fields)
- **Naming Conventions**: Detection of field naming conventions
- **Value Formats**: Recognition of special value formats (dates, UUIDs, URLs)

### Programming Language Parsers

- **Nim Parser**: Added extraction of procedure patterns, type patterns, and naming conventions
- **OCaml Parser**: Enhanced with binding, type, module, and documentation pattern extraction

## 4. Integration Improvements

- **Module Registry**: Updated pattern module registration system
- **Pattern API**: Standardized pattern extraction API across formats
- **Learning Pipeline**: Enhanced pattern extraction in the repository learning pipeline

These changes enable the following capabilities in the reference repository learning system:

- Extracting patterns from documentation and configuration files
- Identifying code structure patterns across languages
- Discovering naming conventions in code files
- Detecting error handling patterns in repositories
- Finding documentation best practices

The pattern extraction system now supports the entire reference repository learning pipeline:

1. Patterns are extracted during repository indexing
2. Patterns are stored in both PostgreSQL and Neo4j
3. Pattern relationships are analyzed using graph algorithms
4. Patterns can be applied to target repositories to improve code quality

## 5. Future Work

- Enhance language-specific parsers (JavaScript, Python, etc.)
- Improve pattern classification and confidence scoring
- Develop better pattern comparison and matching algorithms
- Add more sophisticated pattern relationship analysis
- Enhance pattern application with more specific recommendations

## 6. Usage Examples

Example of extracting patterns from HTML content:

```python
from parsers.custom_parsers import HtmlParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = HtmlParser()

# Extract patterns directly
html_content = "<nav><ul><li><a href='#'>Home</a></li></ul></nav>"
patterns = parser.extract_patterns(html_content)

# Or use the unified API
patterns = extract_patterns_for_learning("html", html_content)
```

Example of extracting patterns from JSON content:

```python
from parsers.custom_parsers import JsonParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = JsonParser()

# Extract patterns directly
json_content = '{"id": 1, "createdAt": "2023-05-01", "status": "active"}'
patterns = parser.extract_patterns(json_content)

# Or use the unified API
patterns = extract_patterns_for_learning("json", json_content)
```

Example of extracting patterns from TOML content:

```python
from parsers.custom_parsers import TomlParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = TomlParser()

# Extract patterns directly
toml_content = """
[package]
name = "repo-analyzer"
version = "1.0.0"

[dependencies]
regex = "1.8.1"
yaml = "0.2.5"
"""
patterns = parser.extract_patterns(toml_content)

# Or use the unified API
patterns = extract_patterns_for_learning("toml", toml_content)
```

Example of extracting patterns from XML content:

```python
from parsers.custom_parsers import XmlParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = XmlParser()

# Extract patterns directly
xml_content = """
<?xml version="1.0" encoding="UTF-8"?>
<root>
  <element id="main">
    <child>Content</child>
    <child>More content</child>
  </element>
</root>
"""
patterns = parser.extract_patterns(xml_content)

# Or use the unified API
patterns = extract_patterns_for_learning("xml", xml_content)
```

Example of extracting patterns from YAML content:

```python
from parsers.custom_parsers import YamlParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = YamlParser()

# Extract patterns directly
yaml_content = """
version: 1.0
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
  database:
    image: postgres:14
    environment:
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
"""
patterns = parser.extract_patterns(yaml_content)

# Or use the unified API
patterns = extract_patterns_for_learning("yaml", yaml_content)
```

Example of extracting patterns from INI content:

```python
from parsers.custom_parsers import IniParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = IniParser()

# Extract patterns directly
ini_content = """
[database]
host = localhost
port = 5432
user = ${DB_USER}
"""
patterns = parser.extract_patterns(ini_content)

# Or use the unified API
patterns = extract_patterns_for_learning("ini", ini_content)
```

Example of extracting patterns from RST content:

```python
from parsers.custom_parsers import RstParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = RstParser()

# Extract patterns directly
rst_content = """
Section Title
============

.. note::
   This is a note directive.

:Author: John Doe
:Version: 1.0

* Bullet point
* Another bullet point
"""
patterns = parser.extract_patterns(rst_content)

# Or use the unified API
patterns = extract_patterns_for_learning("rst", rst_content)
```

Example of extracting patterns from plaintext content:

```python
from parsers.custom_parsers import PlaintextParser
from parsers.query_patterns import extract_patterns_for_learning

# Create a parser instance
parser = PlaintextParser()

# Extract patterns directly
plaintext_content = """
# Main Heading

This is a paragraph with some text.
It continues on multiple lines.

* Item 1
* Item 2

@author: John Doe
@version: 1.0

https://example.com
"""
patterns = parser.extract_patterns(plaintext_content)

# Or use the unified API
patterns = extract_patterns_for_learning("plaintext", plaintext_content)
```
