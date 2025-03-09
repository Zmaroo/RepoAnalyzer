"""Parser interfaces for RepoAnalyzer.

This module defines the core interfaces for the parser system, including base classes
for tree-sitter and custom parsers.
"""

from typing import Dict, Any, List, Optional, Union, Tuple, Set
from abc import ABC, abstractmethod
import asyncio
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks

class BaseParserInterface(ABC):
    """Base interface for all parsers."""
    
    def __init__(self, language_id: str, file_type: FileType, parser_type: ParserType):
        """Initialize base parser interface."""
        self.language_id = language_id
        self.file_type = file_type
        self.parser_type = parser_type
        self._initialized = False
    
    @abstractmethod
    async def parse(self, source_code: str) -> Optional[Dict[str, Any]]:
        """Parse source code into AST."""
        pass
    
    @abstractmethod
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from AST."""
        pass

class AIParserInterface(ABC):
    """Interface for AI-enhanced parsing capabilities."""
    
    def __init__(self, language_id: str, file_type: FileType, capabilities: Set[AICapability]):
        """Initialize AI parser interface."""
        self.language_id = language_id
        self.file_type = file_type
        self.ai_capabilities = capabilities
        self._initialized = False
    
    @abstractmethod
    async def process_with_ai(self, source_code: str, context: AIContext) -> AIProcessingResult:
        """Process source code with AI assistance."""
        pass

# Export public interfaces
__all__ = [
    'BaseParserInterface',
    'AIParserInterface'
] 