# Component-Specific Exception Handling Guide

This guide provides specialized exception handling guidance for different components of the RepoAnalyzer codebase, building on the principles established in the main Exception Handling Guide.

## Table of Contents

1. [Database Operations](#database-operations)
2. [File Parsing and Processing](#file-parsing-and-processing)
3. [AI and Model Interactions](#ai-and-model-interactions)
4. [Web API Components](#web-api-components)
5. [Command-Line Interfaces](#command-line-interfaces)

## Database Operations

### Neo4j Graph Database

Operations with Neo4j should use:

1. The `@with_retry` decorator for transient failures
2. Specific error types from `DatabaseError` hierarchy
3. `AsyncErrorBoundary` context managers for complex operations

```python
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.error_handling import DatabaseError, Neo4jError
from db.retry_utils import with_retry

@with_retry(max_retries=3, backoff_factor=1.5)
@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def create_relationship(from_node_id, to_node_id, rel_type, properties=None):
    """Create a relationship between two nodes with retry.
    
    Args:
        from_node_id: Source node ID
        to_node_id: Target node ID
        rel_type: Relationship type
        properties: Optional relationship properties
        
    Returns:
        Created relationship data or None if failed
    """
    async with AsyncErrorBoundary("relationship creation", error_types=(Neo4jError,)):
        # Format properties for query
        props = {}
        if properties:
            props.update(properties)
            
        query = """
        MATCH (a), (b) 
        WHERE ID(a) = $from_id AND ID(b) = $to_id 
        CREATE (a)-[r:$rel_type $props]->(b) 
        RETURN r
        """
        params = {
            "from_id": from_node_id,
            "to_id": to_node_id,
            "rel_type": rel_type,
            "props": props
        }
        
        return await run_query(query, params)
```

### PostgreSQL Database

PostgreSQL operations should:

1. Use `@handle_async_errors` with `PostgresError` type
2. Ensure proper transaction management
3. Apply retry for connection issues

```python
from utils.error_handling import handle_async_errors, PostgresError
from db.retry_utils import with_retry, is_connection_error

@with_retry(retry_on=is_connection_error)
@handle_async_errors(error_types=PostgresError)
async def store_file_metadata(file_path, metadata):
    """Store file metadata in PostgreSQL with retry for connection issues.
    
    Args:
        file_path: Path to the file
        metadata: Dictionary of metadata to store
        
    Returns:
        Boolean indicating success
    """
    # Implementation
```

## File Parsing and Processing

File processing operations should:

1. Handle `IOError` and `ProcessingError` explicitly
2. Implement fallback mechanisms for parsing failures
3. Utilize error boundaries for multi-step operations

```python
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError, ParsingError

@handle_async_errors(error_types=(ProcessingError, IOError, ParsingError))
async def process_source_file(file_path):
    """Process a source code file with comprehensive error handling.
    
    Args:
        file_path: Path to the file to process
        
    Returns:
        Processed result or None if processing failed
    """
    async with AsyncErrorBoundary(f"processing {file_path}", error_types=(IOError,)):
        # Check if file exists
        if not os.path.exists(file_path):
            raise ProcessingError(f"File not found: {file_path}")
            
        # Read file
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try alternative encoding
            try:
                with open(file_path, 'r', encoding='latin-1') as f:
                    content = f.read()
                    log.warning(f"File {file_path} decoded using fallback encoding latin-1")
            except Exception as e:
                raise ProcessingError(f"Failed to read file {file_path}: {str(e)}")
                
        # Parse content
        async with AsyncErrorBoundary("parsing file content", error_types=(ParsingError,)):
            # Attempt parsing
            # Implementation
            
    # Return result
```

## AI and Model Interactions

AI components should:

1. Handle model-specific errors explicitly
2. Provide fallbacks for model failures
3. Ensure timeout handling

```python
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError
import asyncio

@handle_async_errors(error_types=(ProcessingError, asyncio.TimeoutError))
async def generate_embedding(text, timeout=10):
    """Generate embeddings with timeout and error handling.
    
    Args:
        text: Text to embed
        timeout: Maximum time to wait for embedding generation
        
    Returns:
        Generated embedding or None if failed
    """
    async with AsyncErrorBoundary("embedding generation"):
        try:
            # Set timeout for the embedding operation
            result = await asyncio.wait_for(
                _generate_embedding_internal(text),
                timeout=timeout
            )
            return result
        except asyncio.TimeoutError:
            log.warning(f"Embedding generation timed out after {timeout} seconds")
            raise ProcessingError(f"Embedding generation timed out after {timeout} seconds")
        except Exception as e:
            log.error(f"Error generating embedding: {str(e)}")
            # Try fallback model if primary fails
            try:
                return await _generate_fallback_embedding(text)
            except Exception as fallback_error:
                raise ProcessingError(f"All embedding generation attempts failed: {str(fallback_error)}")
```

## Web API Components

Web API handlers should:

1. Convert internal exceptions to appropriate HTTP responses
2. Use structured error responses
3. Log detailed internal errors but return sanitized messages to clients

```python
from utils.error_handling import handle_async_errors, DatabaseError, ProcessingError

@handle_async_errors(error_types=(Exception,))  # Broad catch at API boundary is acceptable
async def api_get_repository_analysis(request):
    """API endpoint to get repository analysis with error handling.
    
    Args:
        request: HTTP request object
        
    Returns:
        JSON API response
    """
    try:
        repo_id = request.query_params.get('repo_id')
        if not repo_id:
            return create_error_response(400, "Missing required parameter: repo_id")
            
        # Fetch analysis
        try:
            analysis = await fetch_repository_analysis(repo_id)
            return create_success_response(analysis)
        except DatabaseError as e:
            log.error(f"Database error fetching repo analysis: {str(e)}")
            return create_error_response(500, "Database error occurred")
        except ProcessingError as e:
            log.error(f"Processing error in analysis: {str(e)}")
            return create_error_response(500, "Error processing repository data")
    except Exception as e:
        # Unexpected error - log detailed info but return generic message
        log.exception(f"Unhandled exception in API: {str(e)}")
        return create_error_response(500, "An unexpected error occurred")
```

## Command-Line Interfaces

CLI components should:

1. Handle user-facing errors with friendly messages
2. Provide detailed error context when verbose mode is enabled
3. Ensure clean exit with appropriate status codes

```python
from utils.error_handling import handle_errors, ProcessingError, DatabaseError

@handle_errors(error_types=(Exception,))  # Broad catch at CLI boundary is acceptable
def cli_analyze_repository(args):
    """CLI command to analyze a repository with user-friendly error handling.
    
    Args:
        args: Command line arguments
        
    Returns:
        Exit code
    """
    try:
        # Process repository
        repository_path = args.path
        
        # Validate input
        if not os.path.exists(repository_path):
            print(f"Error: Repository path not found: {repository_path}")
            return 1
            
        # Perform analysis
        try:
            print(f"Analyzing repository: {repository_path}")
            result = analyze_repository(repository_path)
            print("Analysis complete!")
            return 0
        except DatabaseError as e:
            print(f"Database error: {str(e)}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 2
        except ProcessingError as e:
            print(f"Processing error: {str(e)}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return 3
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 130
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
```

## Conclusion

By following these component-specific guidelines along with the general Exception Handling Guide, you'll ensure that RepoAnalyzer has consistent, robust error handling throughout the codebase.

Remember to run the exception pattern analyzer regularly to identify areas that need improvement:

```bash
./scripts/analyze_exception_patterns.py --verbose
```
