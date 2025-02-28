# Exception Handling Guide for RepoAnalyzer

This guide outlines the best practices for handling exceptions in the RepoAnalyzer codebase, ensuring consistent, maintainable, and robust error handling throughout the application.

## Table of Contents

1. [Exception Handling Principles](#exception-handling-principles)
2. [Standard Error Types](#standard-error-types)
3. [Error Handling Tools](#error-handling-tools)
4. [Best Practices by Component](#best-practices-by-component)
5. [Auditing and Monitoring](#auditing-and-monitoring)
6. [Examples](#examples)

## Exception Handling Principles

The RepoAnalyzer application follows these core principles for exception handling:

### 1. Explicit over Implicit

- Be explicit about which errors you expect and handle
- Use specific exception types instead of catching all exceptions
- Document expected exceptions in function docstrings

### 2. Fail Fast, Recover Gracefully

- Detect errors as early as possible
- Provide meaningful error messages that aid in debugging
- Ensure the system can continue operating after non-critical errors

### 3. Consistent Patterns

- Use standard utility functions and decorators for error handling
- Apply consistent error logging and reporting
- Categorize errors properly

### 4. Appropriate Error Propagation

- Low-level functions should raise specific exceptions
- Mid-level functions should transform exceptions into domain-specific ones
- High-level functions should handle exceptions and provide user-friendly feedback

## Standard Error Types

RepoAnalyzer defines a hierarchy of exception types to categorize errors appropriately:

``` plaintext
Exception
├── ProcessingError
│   └── ParsingError
└── DatabaseError
    ├── PostgresError
    ├── Neo4jError
    ├── TransactionError
    └── CacheError
```

### When to Use Each Type

- **ProcessingError**: For errors during file processing, extraction, or analysis
- **ParsingError**: Specifically for syntax or parsing failures
- **DatabaseError**: Base class for all database-related errors
- **PostgresError**: Specific to PostgreSQL operations
- **Neo4jError**: Specific to Neo4j graph database operations
- **TransactionError**: For errors in transaction management
- **CacheError**: For cache-related failures

## Error Handling Tools

RepoAnalyzer provides several utility functions for standardized error handling:

### Decorators

#### `@handle_errors(error_types=(Exception,))`

For synchronous functions:

```python
@handle_errors(error_types=(ParsingError,))
def parse_file(file_path):
    # Function body
```

#### `@handle_async_errors(error_types=Exception, default_return=None)`

For asynchronous functions:

```python
@handle_async_errors(error_types=DatabaseError, default_return=False)
async def store_data(data):
    # Function body
```

### Context Managers

#### `ErrorBoundary(operation_name, error_types=(Exception,))`

For synchronous code blocks:

```python
with ErrorBoundary("file processing", error_types=(IOError, ValueError)):
    # Code block
```

#### `AsyncErrorBoundary(operation, error_types=(Exception,))`

For asynchronous code blocks:

```python
async with AsyncErrorBoundary("database operation", error_types=(Neo4jError,)):
    # Async code block
```

## Best Practices by Component

### Database Operations

- Use `@handle_async_errors(error_types=DatabaseError)` for database functions
- Apply retry mechanism for transient errors
- Use `AsyncErrorBoundary` for transaction blocks
- Log detailed error information including query parameters (sanitized)

Example:

```python
@handle_async_errors(error_types=(Neo4jError, TransactionError))
async def update_node(node_id, properties):
    async with AsyncErrorBoundary("node update"):
        # Implementation
```

### File Processing

- Use `@handle_errors(error_types=ProcessingError)` for file processing functions
- Apply fallback mechanisms for parsing errors
- Be explicit about file encoding and format expectations

Example:

```python
@handle_errors(error_types=(ProcessingError, IOError))
def process_file(file_path):
    with ErrorBoundary(f"processing {file_path}"):
        # Implementation
```

### AI and Model Operations

- Handle model-specific exceptions explicitly
- Provide fallback responses when models fail
- Always validate model inputs and outputs

Example:

```python
@handle_async_errors(error_types=ProcessingError)
async def generate_embedding(text):
    async with AsyncErrorBoundary("embedding generation"):
        # Implementation
```

## Auditing and Monitoring

RepoAnalyzer includes built-in tools for monitoring and improving exception handling:

### Exception Audit Tool

Run the exception audit to get insights on error patterns:

```bash
python scripts/run_exception_audit.py --verbose
```

This tool:

- Tracks error occurrences across the codebase
- Identifies areas with high error rates
- Suggests improvements for error handling
- Generates reports on error handling coverage

### Error Reporting and Analysis

- All errors are logged with context via the logging system
- Structured error reports help identify error patterns
- The audit tool helps identify code areas needing improved error handling

## Examples

### Database Retry Example

```python
@with_retry(max_retries=3)  # From db.retry_utils
async def fetch_data(query_params):
    """Fetch data with automatic retry for transient errors.
    
    Args:
        query_params: Parameters for the query
        
    Returns:
        Query results
        
    Raises:
        DatabaseError: If all retries fail or a non-retryable error occurs
    """
    async with AsyncErrorBoundary("data fetching", error_types=(Neo4jError,)):
        return await run_query("MATCH (n) WHERE n.id = $id RETURN n", {"id": query_params["id"]})
```

### File Processing with Fallbacks

```python
@handle_async_errors(error_types=(ProcessingError, IOError))
async def parse_with_fallbacks(file_path, content=None):
    """Parse file with fallback mechanisms.
    
    Args:
        file_path: Path to the file
        content: Optional pre-loaded content
        
    Returns:
        Parsed result or None if all parsing attempts fail
    """
    try:
        # Primary parser
        return await primary_parser.parse(file_path, content)
    except ParsingError as e:
        log(f"Primary parser failed: {e}", level="warning")
        
        # Try alternative parser as fallback
        try:
            return await alternative_parser.parse(file_path, content)
        except Exception as e:
            log(f"Alternative parser also failed: {e}", level="error")
            raise ProcessingError(f"All parsing attempts failed for {file_path}: {e}")
```

### Component Error Handling

```python
class DataProcessor:
    """Process data with comprehensive error handling."""
    
    @handle_errors(error_types=(ProcessingError,))
    def __init__(self, config):
        with ErrorBoundary("initializing data processor"):
            self.config = self._validate_config(config)
            # More initialization
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def process_item(self, item):
        """Process a single item with error handling."""
        async with AsyncErrorBoundary(f"processing item {item.id}"):
            # Processing logic
```

## Conclusion

Following these guidelines ensures that RepoAnalyzer handles errors consistently, making the system more reliable and easier to debug. Use the provided tools and patterns, and run the exception audit regularly to monitor and improve error handling across the codebase.
