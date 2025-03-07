"""Error handling utilities."""

from typing import Type, Tuple, Callable, Any, Dict, List, Optional, Set, Union
from functools import wraps
from contextlib import asynccontextmanager
import inspect
import sys
import traceback
import threading
import asyncio
import os
import json
import time
from datetime import datetime
import logging

# Add error severity levels
class ErrorSeverity:
    """Error severity levels for better error handling."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

# Add health status tracking
class HealthStatus:
    """Health status tracking for error boundaries."""
    OK = "ok"
    DEGRADED = "degraded"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorMetrics:
    """Tracks error metrics and performance."""
    def __init__(self):
        self.error_counts = {level: 0 for level in vars(ErrorSeverity).keys() if not level.startswith('_')}
        self.total_operations = 0
        self.total_errors = 0
        self.performance_data = []
        self._lock = asyncio.Lock()

    async def record_error(self, severity: str):
        """Record an error occurrence."""
        async with self._lock:
            self.error_counts[severity] = self.error_counts.get(severity, 0) + 1
            self.total_errors += 1

    async def record_operation(self, duration: float):
        """Record operation performance."""
        async with self._lock:
            self.total_operations += 1
            self.performance_data.append(duration)

    def get_error_rate(self) -> float:
        """Calculate error rate."""
        if self.total_operations == 0:
            return 0.0
        return self.total_errors / self.total_operations

    def get_health_status(self) -> str:
        """Determine health status based on error rates."""
        error_rate = self.get_error_rate()
        if error_rate == 0:
            return HealthStatus.OK
        elif error_rate < 0.1:
            return HealthStatus.DEGRADED
        elif error_rate < 0.3:
            return HealthStatus.ERROR
        return HealthStatus.CRITICAL

# Global metrics instance
error_metrics = ErrorMetrics()

class ProcessingError(Exception):
    """Base class for processing errors."""
    pass

class ParsingError(ProcessingError):
    """Error during parsing operations."""
    pass

class LoggingError(ProcessingError):
    """Error during logging operations."""
    pass

class DatabaseError(Exception):
    """Base class for database errors."""
    pass

class ConnectionError(DatabaseError):
    """Base class for connection-related errors."""
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
    LoggingError: "logging",
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

@asynccontextmanager
async def AsyncErrorBoundary(operation_name=None, error_types=(Exception,), error_message=None, reraise=True, severity=ErrorSeverity.ERROR):
    """Async context manager for error handling."""
    start_time = time.time()

    # Ensure error_types is a tuple
    if isinstance(error_types, list):
        error_types = tuple(error_types)
    elif not isinstance(error_types, tuple) and isinstance(error_types, type):
        error_types = (error_types,)
    
    # Create a simple container for the error
    class ErrorContainer:
        def __init__(self):
            self.error = None
            self.duration = 0
            self.severity = severity
    
    error_container = ErrorContainer()
    msg_prefix = error_message if error_message else f"Error in {operation_name}"
    
    try:
        yield error_container
    except error_types as e:
        # Record error metrics asynchronously
        await error_metrics.record_error(severity)
        
        # Enhanced error logging with severity
        logging.warning(f"{msg_prefix}: {str(e)}")
        
        # Record the error for audit purposes with severity
        await ErrorAudit.record_error(e, operation_name or "unknown", error_types)
        
        # Store the error
        error_container.error = e
        
        # Check health status and log if degraded
        health_status = error_metrics.get_health_status()
        if health_status != HealthStatus.OK:
            logging.warning(f"Health status degraded to {health_status}")
        
        # Re-raise if requested
        if reraise:
            raise
    finally:
        # Record performance metrics asynchronously
        duration = time.time() - start_time
        error_container.duration = duration
        await error_metrics.record_operation(duration)

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
    
    # Track errors with async safety
    _lock = asyncio.Lock()
    
    # Storage for error occurrences
    _errors: Dict[str, List[Dict]] = {}
    
    # Track locations with raw try/except blocks
    _raw_exception_handlers: Set[str] = set()
    
    # Track error handling coverage
    _decorated_functions: Set[str] = set()
    _all_functions: Set[str] = set()
    
    @classmethod
    async def record_error(cls, error: Exception, operation_name: str, handled_types: Union[Type[Exception], Tuple[Type[Exception], ...], List[Type[Exception]]]) -> None:
        """
        Record an error for audit purposes.
        
        Args:
            error: The exception that was caught
            operation_name: The name of the operation where the error occurred
            handled_types: The type(s) of exceptions that were handled. Can be a single exception type,
                          a tuple of exception types, or a list of exception types.
        """
        async with cls._lock:
            # Ensure handled_types is a tuple
            if isinstance(handled_types, list):
                handled_types = tuple(handled_types)
            elif not isinstance(handled_types, tuple) and not isinstance(handled_types, type):
                try:
                    handled_types = tuple(handled_types)
                except (TypeError, ValueError):
                    handled_types = (Exception,)
            elif isinstance(handled_types, type):
                handled_types = (handled_types,)
            
            error_type = type(error).__name__
            if error_type not in cls._errors:
                cls._errors[error_type] = []
            
            # Get the error category
            category = "unknown"
            for error_cls, cat in ERROR_CATEGORIES.items():
                if isinstance(error, error_cls):
                    category = cat
                    break
            
            # Record the error with context
            cls._errors[error_type].append({
                "message": str(error),
                "location": operation_name,
                "category": category,
                "timestamp": datetime.now().isoformat(),
                "handled_by": [t.__name__ for t in handled_types],
                "traceback": traceback.format_exc()
            })
        
        # Get the current file and line number
        frame = inspect.currentframe()
        try:
            frame = frame.f_back  # Get the caller's frame
            file_path = frame.f_code.co_filename
            line_number = frame.f_lineno
        except (AttributeError, ValueError):
            file_path = "unknown"
            line_number = 0
        finally:
            del frame  # Avoid reference cycles
        
        # Register the error
        await cls.register_raw_exception_handler(file_path, line_number)
    
    @classmethod
    async def register_decorated_function(cls, func_name: str):
        """
        Register a function that uses our error handling decorators.
        
        Args:
            func_name: The name of the decorated function
        """
        async with cls._lock:
            cls._decorated_functions.add(func_name)
    
    @classmethod
    async def register_all_functions(cls, module_name: str):
        """
        Register all functions in a module for coverage analysis.
        
        Args:
            module_name: The name of the module to analyze
        """
        try:
            module = sys.modules.get(module_name)
            if not module:
                return
                
            async with cls._lock:
                for name, obj in inspect.getmembers(module):
                    if inspect.isfunction(obj) or inspect.iscoroutinefunction(obj):
                        cls._all_functions.add(f"{module_name}.{name}")
        except Exception as e:
            logging.error(f"Error registering functions from {module_name}: {e}")
    
    @classmethod
    async def register_raw_exception_handler(cls, file_path: str, line_number: int):
        """
        Register a location with a raw try/except block.
        
        Args:
            file_path: Path to the file containing the try/except
            line_number: Line number where the try/except begins
        """
        async with cls._lock:
            cls._raw_exception_handlers.add(f"{file_path}:{line_number}")
    
    @classmethod
    async def get_error_report(cls) -> Dict:
        """
        Generate a comprehensive error report.
        
        Returns:
            Dict containing error statistics and patterns
        """
        async with cls._lock:
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
    async def get_standardization_recommendations(cls) -> List[Dict]:
        """
        Generate recommendations for standardizing error handling.
        
        Returns:
            List of recommendations with locations and suggested changes
        """
        recommendations = []
        
        async with cls._lock:
            # Identify functions with high error rates
            location_counts = {}
            for error_type, occurrences in cls._errors.items():
                for occurrence in occurrences:
                    location = occurrence.get("location", "unknown")
                    if location not in location_counts:
                        location_counts[location] = 0
                    location_counts[location] += 1
            
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
        
        # Sort recommendations by error count (descending)
        return sorted(recommendations, key=lambda x: x["error_count"], reverse=True)
    
    @classmethod
    async def _get_most_common_category_for_location(cls, location: str) -> str:
        """
        Determine the most common error category for a location.
        
        Args:
            location: The error location to analyze
            
        Returns:
            The most common error category
        """
        category_counts = {}
        
        async with cls._lock:
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
        async with cls._lock:
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
                
                logging.info(f"Error audit report saved to {file_path}")
                return file_path
            except Exception as e:
                logging.error(f"Error saving audit report: {e}")
                return ""
    
    @classmethod
    async def analyze_codebase(cls, directory: str):
        """
        Analyze a directory for error handling patterns.
        
        This scans Python files to identify:
        1. Raw try/except blocks
        2. Functions without error handling
        3. Non-standard error patterns
        
        Args:
            directory: Directory path to analyze
        """
        logging.info("Starting error handling audit...")
        
        try:
            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        await cls._analyze_file(file_path)
            
            logging.info(f"Completed error handling analysis of {directory}")
        except Exception as e:
            logging.error(f"Error analyzing codebase: {e}")
    
    @classmethod
    async def _analyze_file(cls, file_path: str):
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
                    await cls.register_raw_exception_handler(file_path, i + 1)
                
                # Check for our decorators
                elif '@handle_errors' in stripped or '@handle_async_errors' in stripped:
                    # The next line should be a function definition
                    if i + 1 < len(lines) and 'def ' in lines[i + 1]:
                        func_def = lines[i + 1].strip()
                        func_name = func_def.split('def ')[1].split('(')[0].strip()
                        await cls.register_decorated_function(func_name)
                
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
                    
                    async with cls._lock:
                        cls._all_functions.add(full_name)
                        
        except Exception as e:
            logging.error(f"Error analyzing file {file_path}: {e}")

    @classmethod
    async def analyze_error_patterns(cls):
        """Analyze error patterns and suggest improvements."""
        # Implementation for error pattern analysis
        pass

def handle_async_errors(error_types=None, default_return=None):
    """Decorator for handling errors in async functions."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if error_types and not isinstance(e, error_types):
                    raise
                logging.error(f"Error in {func.__name__}: {str(e)}")
                # Create task for error recording
                task = asyncio.create_task(ErrorAudit.record_error(e, func.__name__, error_types))
                try:
                    await task
                except Exception as record_error:
                    logging.error(f"Error recording error: {record_error}")
                return default_return
        return wrapper
    return decorator

@handle_async_errors
async def run_exception_audit(codebase_dir: str = ".") -> Dict:
    """
    Run a comprehensive audit of exception handling across the codebase.
    
    Args:
        codebase_dir: Root directory of the codebase to analyze
        
    Returns:
        Dict with audit results and recommendations
    """
    logging.info("Starting exception handling audit...")
    
    try:
        # Analyze the codebase for error handling patterns
        await ErrorAudit.analyze_codebase(codebase_dir)
        
        # Generate the report
        report = await ErrorAudit.get_error_report()
        recommendations = await ErrorAudit.get_standardization_recommendations()
        
        # Save the report to a file
        await ErrorAudit.save_report()
        
        # Log a summary
        logging.info(
            f"Exception audit complete: found {report['total_errors']} errors "
            f"across {report['unique_error_types']} types with "
            f"{len(recommendations)} recommendations"
        )
        
        return {
            "statistics": report,
            "recommendations": recommendations
        }
    except Exception as e:
        logging.error(f"Error running exception audit: {e}")
        return {
            "statistics": {},
            "recommendations": [],
            "error": str(e)
        }

def handle_errors(error_types=None, default_return=None):
    """Decorator for handling errors in synchronous functions."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if error_types and not isinstance(e, error_types):
                    raise
                logging.error(f"Error in {func.__name__}: {str(e)}")
                # Create task for error recording
                loop = asyncio.get_event_loop()
                task = loop.create_task(ErrorAudit.record_error(e, func.__name__, error_types))
                try:
                    loop.run_until_complete(task)
                except Exception as record_error:
                    logging.error(f"Error recording error: {record_error}")
                return default_return
        return wrapper
    return decorator 