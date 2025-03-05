"""[4.0] AI assistant tools and interfaces package.

Flow:
1. Component Initialization:
   - AIAssistant [4.1]: Main interface
   - CodeUnderstanding [4.2]: Code analysis
   - GraphAnalysis [4.3]: Graph capabilities

2. Integration Points:
   - FileProcessor [2.0]: Code processing
   - SearchEngine [5.0]: Semantic search
   - GraphSync [6.3]: Graph projections and algorithms

3. Error Handling:
   - ProcessingError: AI operations
   - DatabaseError: Storage operations
"""

from utils.error_handling import (
    ProcessingError,
    DatabaseError,
    handle_async_errors,
    AsyncErrorBoundary,
    ErrorSeverity
)

# Import classes but not instances
from .ai_interface import AIAssistant
from .code_understanding import CodeUnderstanding
from .graph_capabilities import GraphAnalysis

__all__ = [
    'AIAssistant',
    'CodeUnderstanding',
    'GraphAnalysis',
    'ProcessingError',
    'DatabaseError',
    'handle_async_errors',
    'AsyncErrorBoundary',
    'ErrorSeverity'
]