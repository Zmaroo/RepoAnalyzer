# Documentation for code_understanding.py

## Module Description

Code understanding and analysis capabilities using GraphCodeBERT and graph analysis.

## Classes

### Class: CodeUnderstanding

Provides code analysis and understanding capabilities using GraphCodeBERT embeddings and graph analysis.

#### Methods

##### `__init__()`

Initializes the code understanding module:

- Initializes graph projections
- Validates language support configuration
- Uses GraphCodeBERT embeddings from code_embedder

##### `async analyze_codebase(repo_id: int) -> Dict[str, Any]`

Performs comprehensive codebase analysis:

- Creates/updates graph projections
- Detects code communities
- Analyzes component centrality
- Manages GraphCodeBERT embeddings

Returns:

```python
{
    "communities": List[Dict],
    "central_components": List[Dict],
    "embedded_files": int
}
```

##### `async get_code_context(file_path: str, repo_id: int) -> Dict[str, Any]`

Gets comprehensive context about a code file:

- Graph-based relationships
- GraphCodeBERT-based similarities
- Component types and references

Returns:

```python
{
    "relationships": List[Dict],
    "similar_files": List[Dict]
}
```

##### `async update_embeddings(file_path: str, repo_id: int, code_content: str) -> None`

Updates both graph and content embeddings:

- Generates new GraphCodeBERT embedding
- Updates database records
- Updates graph projections

##### `cleanup() -> None`

Cleans up resources:

- Closes graph projections
- Resources managed by code_embedder

## Error Handling

Implements comprehensive error handling:

- Async/sync error boundaries
- Database error handling
- Processing error handling

## Configuration

Uses configuration from the `config` package:

- `parser_config` for language support validation

## Dependencies

- `embedding_models.py` for GraphCodeBERT embeddings
- `neo4j_ops` for graph operations
- `neo4j_projections` for graph projections
- `psql` for embedding storage

## Usage Example

```python
from ai_tools.code_understanding import code_understanding

async def analyze_code(repo_id: int, file_path: str):
    try:
        # Get code context
        context = await code_understanding.get_code_context(
            file_path=file_path,
            repo_id=repo_id
        )
        
        # Analyze entire codebase
        analysis = await code_understanding.analyze_codebase(repo_id)
        
        return {
            "context": context,
            "analysis": analysis
        }
    finally:
        code_understanding.cleanup()
```

## Error Types

- `ProcessingError`: General processing errors
- `DatabaseError`: Database operation errors
