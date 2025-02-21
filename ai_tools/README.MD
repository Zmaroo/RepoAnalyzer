# AI Tools Implementation

This directory contains the core implementation of AI-powered code analysis tools.

## Components

### AI Assistant Interface (`ai_interface.py`)

- Unified interface for all AI capabilities
- Combines graph analysis and semantic search
- Documentation analysis and suggestions
- Code structure analysis
- Resource management and cleanup

### Code Understanding (`code_understanding.py`)

- Code semantic analysis using CodeBERT
- Community detection in codebases
- Code similarity analysis
- Embedding generation and management
- Integration with Neo4j and PostgreSQL

### Graph Analysis (`graph_capabilities.py`)

- Code structure analysis using Neo4j
- Dependency tracking and analysis
- Code flow tracing
- Reference analysis
- Graph-based metrics

## Configuration

The AI tools use configuration from the `config` package:

- `parser_config`: Language parser settings
- `neo4j_config`: Graph database settings

## Error Handling

All components implement consistent error handling:

- Async/sync error boundaries
- Specific error types for different failures
- Resource cleanup on errors
- Proper error logging

## Usage Example

```python
from ai_tools.ai_interface import ai_assistant
async def analyze_repo(repo_id: int):
try:
# Perform comprehensive analysis
analysis = await ai_assistant.analyze_repository(repo_id)
# Get specific file context
context = await ai_assistant.get_code_context(
repo_id=repo_id,
file_path="src/main.py"
)
# Analyze documentation
docs = ai_assistant.analyze_documentation(repo_id)
return {
"analysis": analysis,
"context": context,
"documentation": docs
}
finally:
# Always cleanup resources
ai_assistant.close()
'''


## Dependencies
- Neo4j for graph analysis
- PostgreSQL for data storage
- Redis for caching (optional)
- PyTorch for ML models
- Tree-sitter for parsing

## Error Types
- `ProcessingError`: General processing errors
- `DatabaseError`: Database-related errors
- `ParserError`: Code parsing errors

See individual module documentation for detailed API references.
