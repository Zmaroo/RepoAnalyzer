"""Error handling utilities."""

from typing import Type, Tuple, Callable, Any, Dict, List, Optional, Set, Union
from functools import wraps
from contextlib import contextmanager, asynccontextmanager
import inspect
import sys
import traceback
import threading
import asyncio
import os
import json
from datetime import datetime
# The following import is circular, but explicitly used only when needed
# from utils.logger import log

class ProcessingError(Exception):
    """Base class for processing errors."""
    pass

class ParsingError(ProcessingError):
    """Error during parsing operations."""
    pass

class DatabaseError(Exception):
    """Base class for database errors."""
    pass

class PostgresError(DatabaseError):
    """PostgreSQL specific errors."""
    pass

class Neo4jError(DatabaseError):
    """Neo4j specific errors."""
    pass

class RetryableError(DatabaseError):
    """Base class for errors that can be retried."""
    pass

class NonRetryableError(DatabaseError):
    """Base class for errors that should not be retried."""
    pass

class RetryableNeo4jError(RetryableError, Neo4jError):
    """Neo4j error that can be retried (e.g., temporary network issues)."""
    pass

class NonRetryableNeo4jError(NonRetryableError, Neo4jError):
    """Neo4j error that should not be retried (e.g., syntax errors)."""
    pass

class TransactionError(DatabaseError):
    """Transaction coordination errors."""
    pass

class CacheError(DatabaseError):
    """Cache operation errors."""
    pass

# Map of error types to their categories for auditing
ERROR_CATEGORIES = {
    ProcessingError: "processing",
    ParsingError: "parsing",
    DatabaseError: "database",
    PostgresError: "database",
    Neo4jError: "database",
    TransactionError: "database",
    CacheError: "cache",
    RetryableError: "database",
    NonRetryableError: "database",
    RetryableNeo4jError: "database",
    NonRetryableNeo4jError: "database",
    Exception: "general"
}

# The handle_errors function can't use its own decorator since it would create a circular reference
def handle_errors(error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Decorator for handling errors."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Add deprecation warning
            import warnings
            warnings.warn(f"'wrapper' is deprecated, use 'wrapper' instead", DeprecationWarning, stacklevel=2)
            
            try:
                return func(*args, **kwargs)
            except error_types as e:
                from utils.logger import log
                log(f"Error in {func.__name__}: {str(e)}", level="error")
                # Record the error for audit purposes
                ErrorAudit.record_error(e, func.__name__, error_types)
        return wrapper
    return decorator

@asynccontextmanager
async def AsyncErrorBoundary(operation_name: str, error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Async context manager for error boundaries.
    
    This context manager provides a way to handle errors in asynchronous code blocks without
    cluttering the code with multiple try/except blocks. It logs the error with information
    about which operation was being performed when the error occurred.
    
    Unlike the handle_async_errors decorator, this doesn't return a default value or swallow
    the exception - it just logs the error and then re-raises it. This is useful when you 
    want to log errors but still need them to propagate up the call stack.
    
    Args:
        operation_name: A string describing the operation being performed. This appears in the
                 error log to help identify where the error occurred.
        error_types: A tuple of exception types to catch. By default, it catches all exceptions,
                    but you can narrow it to specific error types.
    
    Yields:
        Control to the context body.
    
    Raises:
        Any exceptions caught that match error_types will be logged and then re-raised.
    
    Example:
        ```python
        async def process_data(data):
            async with AsyncErrorBoundary(operation_name="data processing", error_types=(ValueError, TypeError)):
                # If any ValueError or TypeError occurs in this block:
                # 1. It will be logged with the operation name "data processing"
                # 2. The exception will still be raised after logging
                result = await validate_data(data)
                processed = await transform_data(result)
                return processed
        ```
    """
    try:
        yield
    except error_types as e:
        from utils.logger import log
        log(f"Error in {operation_name}: {str(e)}", level="error")
        # Record the error for audit purposes
        ErrorAudit.record_error(e, operation_name, error_types)
        raise

def handle_async_errors(func=None, error_types=Exception, default_return=None):
    """
    Decorator for async functions to handle specified exceptions.
    Can be used as @handle_async_errors or with parameters @handle_async_errors(error_types=...)
    
    Args:
        func: The function to decorate (only used when decorator is applied directly)
        error_types: Exception type or tuple of exception types to catch
        default_return: Value to return if an exception occurs
        
    Returns:
        Decorated function or decorator function
        
    Example:
        ```python
        # Direct usage
        @handle_async_errors
        async def process_data_async(data):
            # Process the data
            return await async_process(data)
            
        # Parameterized usage
        @handle_async_errors(error_types=(ValueError, TypeError))
        async def process_data_async(data):
            # Process the data
            return await async_process(data)
        ```
    """
    import inspect
    from typing import List, Dict, Optional, Awaitable, get_type_hints
    
    # When used as @handle_async_errors without calling (no parentheses)
    if func is not None:
        # This is the direct decorator case - func is the actual function
        @wraps(func)
        async def direct_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                from utils.logger import log
                log(f"Error in {func.__name__}: {e}", level="error")
                
                # Record the error for audit purposes
                ErrorAudit.record_error(e, func.__name__, Exception)
                return None
        
        return direct_wrapper
    
    # When used as @handle_async_errors(error_types=...) with calling (with parentheses)
    else:
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except error_types as e:
                    from utils.logger import log
                    log(f"Error in {func.__name__}: {e}", level="error")
                    
                    # Record the error for audit purposes
                    ErrorAudit.record_error(e, func.__name__, error_types)
                    
                    # If default_return is explicitly provided, use that
                    if default_return is not None:
                        return default_return
                    
                    # Otherwise, try to determine an appropriate return type
                    return_type = None
                    try:
                        signature = inspect.signature(func)
                        return_type = signature.return_annotation
                    except (ValueError, TypeError) as e:
                        # These are the most common exceptions that can occur during signature inspection
                        from utils.logger import log
                        log(f"Error getting function signature for {func.__name__}: {e}", level="debug")
                    
                    # Handle different return types
                    if return_type == bool:
                        return False
                    elif return_type in (int, float):
                        return 0
                    elif return_type == str:
                        return ""
                    elif return_type == list or str(return_type).startswith("typing.List"):
                        return []
                    elif return_type == dict or str(return_type).startswith("typing.Dict"):
                        return {}
                    elif return_type == set or str(return_type).startswith("typing.Set"):
                        return set()
                    elif return_type == tuple or str(return_type).startswith("typing.Tuple"):
                        return ()
                    else:
                        return None
                        
            return wrapper
            return decorator

@contextmanager
def ErrorBoundary(operation_name: str, error_types: Tuple[Type[Exception], ...] = (Exception,)):
    """Context manager for error handling."""
    try:
        yield
    except error_types as e:
        from utils.logger import log
        log(f"Error in {operation_name}: {str(e)}", level="error")
        # Record the error for audit purposes
        ErrorAudit.record_error(e, operation_name, error_types)
        raise

# New class for exception auditing
class ErrorAudit:
    """
    Tracks and analyzes exception patterns across the application.
    
    This class provides utilities to:
    1. Record and track exceptions that occur
    2. Generate reports on exception patterns
    3. Identify code areas that need improved error handling
    4. Recommend standardization of error handling
    """
    
    # Track errors with thread safety
    _lock = threading.RLock()
    _async_lock = asyncio.Lock()
    
    # Storage for error occurrences
    _errors: Dict[str, List[Dict]] = {}
    
    # Track locations with raw try/except blocks
    _raw_exception_handlers: Set[str] = set()
    
    # Track error handling coverage
    _decorated_functions: Set[str] = set()
    _all_functions: Set[str] = set()
    
    # Periodic reporting
    _last_report_time: datetime = None
    _reporting_task = None
    _reporting_interval: int = 86400  # Default to daily (in seconds)
    
    @classmethod
    def start_periodic_reporting(cls, interval: int = 86400, report_file: str = None):
        """
        Start periodic error reporting.
        
        Args:
            interval: Time between reports in seconds (default: 86400 - daily)
            report_file: Path to save reports (default: logs/error_report_{timestamp}.json)
        """
        cls._reporting_interval = interval
        
        # Cancel any existing reporting task
        if cls._reporting_task:
            cls._reporting_task.cancel()
        
        async def _reporting_loop():
            while True:
                await asyncio.sleep(cls._reporting_interval)
                await cls.save_report(report_file)
                from utils.logger import log
                log("Generated periodic error audit report", level="info")
                
        # Start new reporting task
        from utils.async_runner import submit_async_task
        cls._reporting_task = submit_async_task(_reporting_loop())
        cls._last_report_time = datetime.now()
        
        from utils.logger import log
        log(f"Started periodic error reporting every {interval} seconds", level="info")
    
    @classmethod
    def stop_periodic_reporting(cls):
        """Stop periodic error reporting."""
        if cls._reporting_task:
            cls._reporting_task.cancel()
            cls._reporting_task = None
            
            from utils.logger import log
            log("Stopped periodic error reporting", level="info")
    
    @classmethod
    def record_error(cls, error: Exception, location: str, handled_types: Union[Type[Exception], Tuple[Type[Exception], ...]] = (Exception,)):
        """
        Record an error occurrence for auditing.
        
        Args:
            error: The exception that occurred
            location: Where the error occurred (function name or operation description)
            handled_types: What exception types were being handled
        """
        with cls._lock:
            error_type = type(error).__name__
            if error_type not in cls._errors:
                cls._errors[error_type] = []
            
            # Get the error category
            category = "unknown"
            for error_cls, cat in ERROR_CATEGORIES.items():
                if isinstance(error, error_cls):
                    category = cat
                    break
            
            # Convert single exception type to a tuple for consistent handling
            if not isinstance(handled_types, tuple):
                handled_types = (handled_types,)
            
            # Record the error with context
            cls._errors[error_type].append({
                "message": str(error),
                "location": location,
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "handled_by": [t.__name__ for t in handled_types],
                "traceback": traceback.format_exc()
            })
    
    @classmethod
    def register_decorated_function(cls, func_name: str):
        """
        Register a function that uses our error handling decorators.
        
        Args:
            func_name: The name of the decorated function
        """
        with cls._lock:
            cls._decorated_functions.add(func_name)
    
    @classmethod
    def register_all_functions(cls, module_name: str):
        """
        Register all functions in a module for coverage analysis.
        
        Args:
            module_name: The name of the module to analyze
        """
        try:
            module = sys.modules.get(module_name)
            if not module:
                return
                
            with cls._lock:
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                        cls._all_functions.add(f"{module_name}.{name}")
        except Exception as e:
            from utils.logger import log
            log(f"Error registering functions from {module_name}: {e}", level="error")
    
    @classmethod
    def register_raw_exception_handler(cls, file_path: str, line_number: int):
        """
        Register a location with a raw try/except block.
        
        Args:
            file_path: Path to the file containing the try/except
            line_number: Line number where the try/except begins
        """
        with cls._lock:
            cls._raw_exception_handlers.add(f"{file_path}:{line_number}")
    
    @classmethod
    def get_error_report(cls) -> Dict:
        """
        Generate a comprehensive error report.
        
        Returns:
            Dict containing error statistics and patterns
        """
        with cls._lock:
            # Count errors by type
            error_counts = {error_type: len(occurrences) 
                           for error_type, occurrences in cls._errors.items()}
            
            # Count errors by category
            category_counts = {}
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    category = occurrence.get("category", "unknown")
                    if category not in category_counts:
                        category_counts[category] = 0
                    category_counts[category] += 1
            
            # Most common error locations
            location_counts = {}
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    location = occurrence.get("location", "unknown")
                    if location not in location_counts:
                        location_counts[location] = 0
                    location_counts[location] += 1
            
            # Sort locations by error frequency
            sorted_locations = sorted(
                location_counts.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            # Calculate error handling coverage
            total_functions = len(cls._all_functions)
            decorated_count = len(cls._decorated_functions)
            coverage_pct = 0
            if total_functions > 0:
                coverage_pct = (decorated_count / total_functions) * 100
                
            return {
                "total_errors": sum(error_counts.values()),
                "unique_error_types": len(error_counts),
                "error_counts_by_type": error_counts,
                "error_counts_by_category": category_counts,
                "top_error_locations": sorted_locations[:10],  # Top 10 locations
                "raw_exception_handlers": len(cls._raw_exception_handlers),
                "error_handling_coverage": {
                    "total_functions": total_functions,
                    "decorated_functions": decorated_count,
                    "coverage_percentage": coverage_pct
                }
            }
    
    @classmethod
    def get_standardization_recommendations(cls) -> List[Dict]:
        """
        Generate recommendations for standardizing error handling.
        
        Returns:
            List of recommendations with locations and suggested changes
        """
        recommendations = []
        
        with cls._lock:
            # Identify functions with high error rates
            location_counts = {}
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    location = occurrence.get("location", "unknown")
                    if location not in location_counts:
                        location_counts[location] = 0
                    location_counts[location] += 1
            
            # Track parameter patterns in error handling
            parameter_patterns = {}
            inconsistent_parameters = set()
            
            # Analyze parameter patterns
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    handled_by = occurrence.get("handled_by", [])
                    location = occurrence.get("location", "unknown")
                    
                    # Track parameter patterns (tuple vs single error type)
                    if len(handled_by) > 0:
                        pattern = "tuple" if len(handled_by) > 1 else "single"
                        if location not in parameter_patterns:
                            parameter_patterns[location] = pattern
                        elif parameter_patterns[location] != pattern:
                            inconsistent_parameters.add(location)
            
            # Recommend parameter standardization
            if inconsistent_parameters:
                recommendations.append({
                    "type": "parameter_standardization",
                    "issue": "Inconsistent error type parameters",
                    "locations": list(inconsistent_parameters),
                    "recommendation": "Standardize error_types parameter to use tuples consistently",
                    "priority": "high"
                })
            
            # Recommend decorators for high-error functions
            for location, count in location_counts.items():
                if count >= 3 and location not in cls._decorated_functions:
                    # Determine the most appropriate decorator based on error types
                    most_common_category = cls._get_most_common_category_for_location(location)
                    decorator = "handle_errors"
                    
                    if most_common_category == "database":
                        decorator = "handle_async_errors(error_types=DatabaseError)"
                    elif most_common_category == "processing":
                        decorator = "handle_async_errors(error_types=ProcessingError)"
                    
                    recommendations.append({
                        "location": location,
                        "issue": "High error rate without standardized handling",
                        "recommendation": f"Apply @{decorator} decorator",
                        "error_count": count
                    })
            
            # Identify raw try/except blocks that should use context managers
            for handler_location in cls._raw_exception_handlers:
                recommendations.append({
                    "location": handler_location,
                    "issue": "Raw try/except block",
                    "recommendation": "Replace with ErrorBoundary or AsyncErrorBoundary context manager",
                    "error_count": 0  # We don't have error counts for these
                })
                
            # Check for modules with inconsistent handling patterns
            module_patterns = {}
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    location = occurrence.get("location", "unknown")
                    module = location.split('.')[0] if '.' in location else location
                    
                    if "handled_by" in occurrence:
                        handler = "decorator" if any(d in location for d in ["handle_errors", "handle_async_errors"]) else "context_manager"
                        
                        if module not in module_patterns:
                            module_patterns[module] = set()
                        module_patterns[module].add(handler)
            
            # Recommend standardizing handling within modules
            for module, patterns in module_patterns.items():
                if len(patterns) > 1:
                    recommendations.append({
                        "type": "module_standardization",
                        "module": module,
                        "issue": "Inconsistent error handling patterns within module",
                        "recommendation": "Standardize error handling approach across the module",
                        "priority": "medium"
                    })
        
        # Sort recommendations by error count (descending)
        return sorted(recommendations, key=lambda x: x.get("error_count", 0), reverse=True)
    
    @classmethod
    def _get_most_common_category_for_location(cls, location: str) -> str:
        """
        Determine the most common error category for a location.
        
        Args:
            location: The error location to analyze
            
        Returns:
            The most common error category
        """
        category_counts = {}
        
        for error_type, occurrences in cls._errors.items():
            for occurrence in occurrences:
                if occurrence.get("location") == location:
                    category = occurrence.get("category", "unknown")
                    if category not in category_counts:
                        category_counts[category] = 0
                    category_counts[category] += 1
        
        if not category_counts:
            return "general"
            
        # Return the most common category
        return max(category_counts.items(), key=lambda x: x[1])[0]
    
    @classmethod
    async def save_report(cls, file_path: str = None) -> str:
        """
        Save the error report to a file.
        
        Args:
            file_path: Optional custom file path. If None, uses default path.
            
        Returns:
            The path to the saved report file
        """
        async with cls._async_lock:
            # Generate the report
            report = cls.get_error_report()
            recommendations = cls.get_standardization_recommendations()
            
            full_report = {
                "timestamp": datetime.now().isoformat(),
                "statistics": report,
                "recommendations": recommendations
            }
            
            # Determine file path
            if file_path is None:
                # Create reports directory if needed
                reports_dir = "reports/errors"
                os.makedirs(reports_dir, exist_ok=True)
                
                # Use timestamped filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                file_path = f"{reports_dir}/error_audit_{timestamp}.json"
            
            # Write to file
            try:
                # Use built-in open since we're just writing once
                with open(file_path, 'w') as f:
                    json.dump(full_report, f, indent=2)
                
                from utils.logger import log
                log(f"Error audit report saved to {file_path}", level="info")
                return file_path
            except Exception as e:
                from utils.logger import log
                log(f"Error saving audit report: {e}", level="error")
                return ""
    
    @classmethod
    def analyze_codebase(cls, directory: str):
        """
        Analyze a directory for error handling patterns.
        
        This scans Python files to identify:
        1. Raw try/except blocks
        2. Functions without error handling
        3. Non-standard error patterns
        
        Args:
            directory: Directory path to analyze
        """
        from utils.logger import log
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        cls._analyze_file(file_path)
            
            log(f"Completed error handling analysis of {directory}", level="info")
        except Exception as e:
            log(f"Error analyzing codebase: {e}", level="error")
    
    @classmethod
    def _analyze_file(cls, file_path: str):
        """
        Analyze a Python file for error handling patterns.
        
        Args:
            file_path: Path to the Python file
        """
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
            
            # Look for raw try/except blocks
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped == 'try:':
                    # Register this as a raw try/except
                    cls.register_raw_exception_handler(file_path, i + 1)
                
                # Check for our decorators
                elif '@handle_errors' in stripped or '@handle_async_errors' in stripped:
                    # The next line should be a function definition
                    if i + 1 < len(lines) and 'def ' in lines[i + 1]:
                        func_def = lines[i + 1].strip()
                        func_name = func_def.split('def ')[1].split('(')[0].strip()
                        cls.register_decorated_function(func_name)
                
                # Check for context managers
                elif 'with ErrorBoundary' in stripped or 'with AsyncErrorBoundary' in stripped:
                    # This is using our context managers
                    pass
                
                # Look for function definitions to track all functions
                elif stripped.startswith('def '):
                    # Extract module name from file path
                    module_path = file_path.replace('/', '.').replace('\\', '.')
                    if module_path.endswith('.py'):
                        module_path = module_path[:-3]
                    
                    # Extract function name
                    func_name = stripped.split('def ')[1].split('(')[0].strip()
                    full_name = f"{module_path}.{func_name}"
                    
                    with cls._lock:
                        cls._all_functions.add(full_name)
                        
        except Exception as e:
            from utils.logger import log
            log(f"Error analyzing file {file_path}: {e}", level="error")

@handle_async_errors
async def run_exception_audit(codebase_dir: str = ".") -> Dict:
    """
    Run a comprehensive audit of exception handling across the codebase.
    
    Args:
        codebase_dir: Root directory of the codebase to analyze
        
    Returns:
        Dict with audit results and recommendations
    """
    from utils.logger import log
    
    try:
        log("Starting exception handling audit...", level="info")
        
        # Analyze the codebase for error handling patterns
        ErrorAudit.analyze_codebase(codebase_dir)
        
        # Generate the report
        report = ErrorAudit.get_error_report()
        recommendations = ErrorAudit.get_standardization_recommendations()
        
        # Save the report to a file
        await ErrorAudit.save_report()
        
        # Log a summary
        log(
            f"Exception audit complete: found {report['total_errors']} errors "
            f"across {report['unique_error_types']} types with "
            f"{len(recommendations)} recommendations",
            level="info"
        )
        
        return {
            "statistics": report,
            "recommendations": recommendations
        }
    except Exception as e:
        log(f"Error running exception audit: {e}", level="error")
        return {
            "statistics": {},
            "recommendations": [],
            "error": str(e)
        } 