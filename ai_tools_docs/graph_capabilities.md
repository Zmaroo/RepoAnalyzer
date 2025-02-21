# Documentation for graph_capabilities.py

## Module Description

Neo4j Graph Analysis Capabilities for code analysis and understanding.

## Classes

### Class: GraphAnalysis

Provides graph-based code analysis capabilities using Neo4j.

#### Methods

##### `__init__()`

Initializes the graph analysis tools:

- Sets up Neo4j connections
- Initializes graph projections
- Validates Neo4j configuration

##### `async get_code_metrics(repo_id: int, file_path: Optional[str] = None) -> Dict[str, Any]`

Gets code metrics from graph analysis:

- Outgoing dependencies
- Total dependencies
- Complexity metrics
- File-specific metrics when file_path is provided

Returns:

```python
{
    "file_path": str,
    "outgoing_deps": int,
    "dependencies": int,
    "complexity": int
}
```

##### `async get_dependencies(repo_id: int, file_path: Optional[str] = None, depth: int = 2) -> List[Dict[str, Any]]`

Gets code dependencies up to specified depth:

- Direct dependencies
- Transitive dependencies
- Relationship types

Returns:

```python
[
    {
        "source": str,
        "target": str,
        "type": str
    }
]
```

##### `async get_references(repo_id: int, file_path: str) -> List[Dict[str, Any]]`

Gets all references to a specific file:

- Incoming references
- Reference types
- Source files

Returns:

```python
[
    {
        "source": str,
        "type": str
    }
]
```

##### `async trace_code_flow(entry_point: str, repo_id: int, max_depth: int = 5) -> List[Dict[str, Any]]`

Traces code flow from an entry point:

- Call paths
- Import chains
- Maximum depth control

Returns:

```python
[
    {
        "nodes": [{"file_path": str}],
        "relationships": [{"type": str}]
    }
]
```

##### `close() -> None`

Closes Neo4j connections and cleans up resources.

## Error Handling

Implements comprehensive error handling:

- Async/sync error boundaries
- Database error handling
- Processing error handling
- Connection error handling

## Configuration

Uses configuration from the `config` package:

- `neo4j_config` for database connection settings

## Dependencies

- `neo4j_ops` for database operations
- `neo4j_projections` for graph projections
- `error_handling` for error management

## Usage Example

```python
from ai_tools.graph_capabilities import graph_analysis

async def analyze_dependencies(repo_id: int, file_path: str):
    try:
        # Get code metrics
        metrics = await graph_analysis.get_code_metrics(
            repo_id=repo_id,
            file_path=file_path
        )
        
        # Get dependencies
        deps = await graph_analysis.get_dependencies(
            repo_id=repo_id,
            file_path=file_path,
            depth=3
        )
        
        # Trace code flow
        flow = await graph_analysis.trace_code_flow(
            entry_point=file_path,
            repo_id=repo_id
        )
        
        return {
            "metrics": metrics,
            "dependencies": deps,
            "code_flow": flow
        }
    finally:
        graph_analysis.close()
```

## Error Types

- `ProcessingError`: General processing errors
- `DatabaseError`: Neo4j operation errors
- `ConnectionError`: Database connection errors
