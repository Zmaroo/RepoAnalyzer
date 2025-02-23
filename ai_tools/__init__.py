"""[4.0] AI assistant tools and interfaces package.

Flow:
1. Component Initialization:
   - AIAssistant [4.1]: Main interface
   - CodeUnderstanding [4.2]: Code analysis
   - GraphAnalysis [4.3]: Graph capabilities

2. Integration Points:
   - FileProcessor [2.0]: Code processing
   - SearchEngine [5.0]: Semantic search
   - GraphSync [6.3]: Graph projections

3. Error Handling:
   - ProcessingError: AI operations
   - DatabaseError: Storage operations
"""

from utils.error_handling import (
    ProcessingError,
    DatabaseError,
    handle_async_errors,
    AsyncErrorBoundary
)

from .ai_interface import AIAssistant, ai_assistant
from .code_understanding import CodeUnderstanding, code_understanding
from .graph_capabilities import GraphAnalysis, graph_analysis

__all__ = [
    'AIAssistant',
    'ai_assistant',
    'CodeUnderstanding',
    'code_understanding',
    'GraphAnalysis',
    'graph_analysis'
]