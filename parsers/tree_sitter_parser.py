"""Tree-sitter parser implementation.

This module provides the tree-sitter based parser implementation, integrating with
tree-sitter-language-pack for efficient parsing capabilities.
"""

from typing import Dict, Optional, Set, List, Any, Union, TYPE_CHECKING
import asyncio
import time
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel,
    ParserResult, PatternValidationResult
)
from parsers.models import FileClassification, BaseNodeDict
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from utils.logger import log
from utils.error_handling import (
    AsyncErrorBoundary,
    handle_async_errors,
    ProcessingError,
    ErrorAudit,
    ErrorSeverity
)
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor, monitor_operation
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context, cached_in_request
from db.transaction import transaction_scope, get_transaction_coordinator

if TYPE_CHECKING:
    from parsers.base_parser import BaseParser

class TreeSitterParser(BaseParserInterface, AIParserInterface):
    """Tree-sitter based parser implementation.
    
    This class implements both BaseParserInterface and AIParserInterface to provide
    tree-sitter specific parsing capabilities with AI support.
    
    Attributes:
        language_id (str): The identifier for the language this parser handles
        file_type (FileType): The type of files this parser can process
        parser_type (ParserType): Always TREE_SITTER for this implementation
        _parser: The tree-sitter parser instance
        _language: The tree-sitter language instance
        _binding: The tree-sitter binding instance
    """
    
    def __init__(self, language_id: str):
        """Initialize tree-sitter parser.
        
        Args:
            language_id: The identifier for the language this parser handles
        """
        # Initialize BaseParserInterface
        BaseParserInterface.__init__(
            self,
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.TREE_SITTER
        )
        
        # Initialize AIParserInterface
        AIParserInterface.__init__(
            self,
            language_id=language_id,
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        
        self._parser = None
        self._language = None
        self._binding = None
        self._pending_tasks: Set[asyncio.Task] = set()
    
    async def initialize(self) -> bool:
        """Initialize the tree-sitter parser.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Wait for database initialization
            transaction_coordinator = await get_transaction_coordinator()
            if not await transaction_coordinator.is_ready():
                await log(f"Database not ready for {self.language_id} parser", level="warning")
                return False
            
            async with AsyncErrorBoundary(f"tree_sitter_initialization_{self.language_id}"):
                # Check if language is supported
                if self.language_id not in SupportedLanguage.__args__:
                    raise ProcessingError(f"Language {self.language_id} not supported by tree-sitter")
                
                # Initialize tree-sitter components through async_runner
                init_task = submit_async_task(self._initialize_components())
                self._pending_tasks.add(init_task)
                try:
                    await asyncio.wrap_future(init_task)
                finally:
                    self._pending_tasks.remove(init_task)
                
                if not all([self._parser, self._language, self._binding]):
                    raise ProcessingError(f"Failed to initialize tree-sitter for {self.language_id}")
                
                await log(f"Tree-sitter components initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing tree-sitter components: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"tree_sitter_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"tree_sitter_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize tree-sitter components for {self.language_id}: {e}")
    
    async def _cleanup(self) -> None:
        """Clean up tree-sitter parser resources."""
        try:
            # Update status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Cancel any pending tasks
            for task in self._pending_tasks.copy():
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to complete with timeout
            if self._pending_tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._pending_tasks, return_exceptions=True),
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    await log(f"Timeout waiting for tasks to complete in {self.language_id} tree-sitter parser", level="warning")
                except Exception as e:
                    await log(f"Error waiting for tasks in {self.language_id} tree-sitter parser: {e}", level="error")
                finally:
                    self._pending_tasks.clear()
            
            # Clean up tree-sitter components
            self._parser = None
            self._language = None
            self._binding = None
            
            await log(f"Tree-sitter parser cleaned up for {self.language_id}", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
            
        except Exception as e:
            await log(f"Error cleaning up tree-sitter parser: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup tree-sitter parser: {e}")
    
    async def _initialize_components(self) -> None:
        """Initialize tree-sitter components."""
        self._parser = get_parser(self.language_id)
        self._language = get_language(self.language_id)
        self._binding = get_binding(self.language_id)
    
    @handle_async_errors(error_types=ProcessingError)
    async def _parse_source(self, source_code: str) -> Dict[str, Any]:
        """Parse source code using tree-sitter.
        
        Args:
            source_code: The source code to parse
            
        Returns:
            Dict[str, Any]: The parsed AST
            
        Raises:
            ProcessingError: If parsing fails
        """
        try:
            async with AsyncErrorBoundary(f"tree_sitter_parse_{self.language_id}"):
                # Parse with tree-sitter through async_runner
                parse_task = submit_async_task(self._parse_with_tree_sitter(source_code))
                tree = await asyncio.wrap_future(parse_task)
                
                if not tree or not tree.root_node:
                    raise ProcessingError("Tree-sitter parsing failed")
                
                # Convert to our AST format
                ast = self._convert_node(tree.root_node)
                
                return ast
                
        except Exception as e:
            await log(f"Error in tree-sitter parsing: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"tree_sitter_parse_{self.language_id}",
                ProcessingError,
                context={"source_size": len(source_code)}
            )
            raise ProcessingError(f"Tree-sitter parsing failed: {e}")
    
    async def _parse_with_tree_sitter(self, source_code: str) -> Any:
        """Parse source code with tree-sitter in a separate task."""
        return self._parser.parse(bytes(source_code, "utf8"))
    
    def _convert_node(self, node: Any) -> Dict[str, Any]:
        """Convert a tree-sitter node to our AST format.
        
        Args:
            node: The tree-sitter node to convert
            
        Returns:
            Dict[str, Any]: The converted AST node
        """
        return self._create_node(
            node_type=node.type,
            start_point=list(node.start_point),
            end_point=list(node.end_point),
            children=[self._convert_node(child) for child in node.children],
            metadata={
                "named": node.is_named,
                "error": node.has_error,
                "missing": node.is_missing
            }
        )
    
    async def _validate_ast(self, ast: Dict[str, Any]) -> List[str]:
        """Validate AST structure.
        
        Args:
            ast: The AST to validate
            
        Returns:
            List[str]: List of validation errors
        """
        errors = []
        
        # Check for basic structure
        if not ast or not isinstance(ast, dict):
            errors.append("Invalid AST structure")
            return errors
        
        # Check required fields
        required_fields = ["type", "start_point", "end_point", "children"]
        for field in required_fields:
            if field not in ast:
                errors.append(f"Missing required field: {field}")
        
        # Check for parsing errors
        if ast.get("metadata", {}).get("error"):
            errors.append(f"Node {ast['type']} has parsing errors")
        
        # Recursively validate children
        for child in ast.get("children", []):
            child_errors = await self._validate_ast(child)
            errors.extend(child_errors)
        
        return errors
    
    async def _extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from AST using tree-sitter capabilities.
        
        Args:
            ast: The AST to extract features from
            source_code: The original source code
            
        Returns:
            ExtractedFeatures: The extracted features
        """
        features = await super()._extract_features(ast, source_code)
        
        # Add tree-sitter specific features
        if self._language and self._binding:
            try:
                # Extract additional features through tree-sitter queries
                query_task = submit_async_task(self._extract_tree_sitter_features(ast))
                ts_features = await asyncio.wrap_future(query_task)
                features.update(ts_features)
            except Exception as e:
                await log(f"Error extracting tree-sitter features: {e}", level="warning")
        
        return features
    
    async def _extract_tree_sitter_features(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features using tree-sitter specific capabilities."""
        features = {}
        
        # Add tree-sitter specific feature extraction
        # This is a placeholder - subclasses should implement language-specific extraction
        
        return features

# Global instance cache
_parser_instances: Dict[str, TreeSitterParser] = {}

async def get_tree_sitter_parser(language_id: str) -> Optional[TreeSitterParser]:
    """Get a tree-sitter parser instance for a language.
    
    Args:
        language_id: The language to get a parser for
        
    Returns:
        Optional[TreeSitterParser]: The parser instance or None if initialization fails
    """
    if language_id not in _parser_instances:
        parser = TreeSitterParser(language_id)
        if await parser.initialize():
            _parser_instances[language_id] = parser
        else:
            return None
    return _parser_instances[language_id] 