# AI Tools Implementation

This directory contains the core implementation of AI-powered code analysis tools.

## Components

### AI Assistant Interface (`ai_interface.py`)

- Unified interface for all AI capabilities
- Combines graph analysis and semantic search
- Documentation analysis and suggestions
- Code structure analysis
- Reference repository learning
- Resource management and cleanup

### Code Understanding (`code_understanding.py`)

- Code semantic analysis using CodeBERT
- Community detection in codebases
- Code similarity analysis
- Embedding generation and management
- Integration with Neo4j and PostgreSQL
- Uses GraphSync for projection management

### Graph Analysis (`graph_capabilities.py`)

- Code structure analysis using Neo4j GDS
- Dependency tracking and analysis
- Code flow tracing
- Reference analysis
- Graph-based metrics
- Centralized graph projection management via GraphSync

### Reference Repository Learning (`reference_repository_learning.py`)

- Pattern extraction from reference repositories
- Best practice identification
- Documentation convention analysis
- Architecture pattern recognition
- Pattern-based recommendations
- Cross-repository learning
- Graph-based pattern analysis

## Configuration

The AI tools use configuration from the `config` package:

- `parser_config`: Language parser settings
- `neo4j_config`: Graph database settings
- `rule_config`: Pattern learning rules

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
        
        # Learn from reference repository
        reference_repo_id = 123  # ID of reference repo
        patterns = await ai_assistant.learn_from_reference_repo(reference_repo_id)
        
        # Apply patterns to target repository
        recommendations = await ai_assistant.apply_reference_patterns(
            reference_repo_id,
            repo_id
        )
        
        return {
            "analysis": analysis,
            "context": context,
            "documentation": docs,
            "patterns": patterns,
            "recommendations": recommendations
        }
    finally:
        # Always cleanup resources
        ai_assistant.close()
```

## Dependencies

- Neo4j for graph analysis
- PostgreSQL for data storage
- Redis for caching (optional)
- PyTorch for ML models
- Tree-sitter for parsing

## Graph Management

The tools use a centralized graph management system through the GraphSync module:

- Projection creation and updates
- Cache state management
- Graph algorithm coordination
- Asynchronous task management

## Error Types

- `ProcessingError`: General processing errors
- `DatabaseError`: Database-related errors
- `ParserError`: Code parsing errors
- `Neo4jError`: Graph database errors
- `TransactionError`: Transaction-related errors

See individual module documentation for detailed API references.
