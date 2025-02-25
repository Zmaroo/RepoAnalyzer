# Reference Repository Learning

## Overview

The Reference Repository Learning module enables AI assistants to extract patterns, best practices, and conventions from high-quality reference repositories. This helps AI assistants provide more contextually relevant recommendations based on existing code patterns when developing new projects.

## Key Features

- **Pattern Extraction**: Identifies code patterns, documentation conventions, and architecture designs from reference repositories.
- **Cross-Repository Learning**: Applies learned patterns from reference repositories to target projects.
- **Intelligent Recommendations**: Generates recommendations based on similarities between target projects and reference patterns.

## Components

### Pattern Types

1. **Code Patterns**
   - Syntactic structures and common coding idioms
   - Language-specific conventions
   - Error handling patterns
   - Function and class structures

2. **Documentation Patterns**
   - Documentation style and conventions
   - Common headers and structures
   - Inline documentation formats
   - API documentation standards

3. **Architecture Patterns**
   - Directory structure organization
   - Component relationships
   - Dependency management
   - Module boundaries

## Usage

### Command Line Interface

```bash
# Learn from a reference repository
python index.py --learn-ref /path/to/reference/repo

# Apply patterns from a reference repository to the current project
python index.py --learn-ref /path/to/reference/repo --apply-ref-patterns

# Clone and learn from a GitHub repository
python index.py --learn-ref https://github.com/user/repo --apply-ref-patterns
```

### API Usage

```python
from ai_tools.ai_interface import ai_assistant

# Learn from a reference repository
patterns = await ai_assistant.learn_from_reference_repo(reference_repo_id)

# Apply patterns to a target project
recommendations = await ai_assistant.apply_reference_patterns(
    reference_repo_id,
    target_repo_id
)

# Analyze with reference
combined_analysis = await ai_assistant.analyze_repository_with_reference(
    repo_id,
    reference_repo_id
)
```

## Implementation Details

### Pattern Extraction

The pattern extraction process analyzes:

1. Code structures via AST analysis
2. Documentation formats and structures
3. Directory and file organization patterns
4. Component dependency relationships

Patterns are stored in the database for later retrieval and application.

### Pattern Application

When applying patterns to a target project:

1. The system analyzes the target project structure
2. It identifies similarities and differences with reference patterns
3. It generates recommendations based on reference patterns
4. The recommendations are formatted for AI consumption

## Integration Points

- **Code Understanding**: Utilizes code analysis to extract patterns
- **Graph Analysis**: Uses graph relationships to understand dependencies
- **Embedding Models**: Creates vector representations of code for comparison
- **Neo4j**: Stores and analyzes structural relationships

## Database Schema

Patterns are stored in three main tables:

- `code_patterns`: For storing code-level patterns
- `doc_patterns`: For storing documentation patterns
- `arch_patterns`: For storing architecture patterns

## Future Enhancements

- **Pattern Ranking**: Improve pattern ranking based on usage frequency
- **Multi-Repository Learning**: Learn from multiple repositories simultaneously
- **Interactive Pattern Application**: Allow users to accept/reject individual pattern applications
- **Pattern Validation**: Validate applied patterns by analyzing code metrics
