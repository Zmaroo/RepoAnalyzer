"""[4.0] Tree-sitter based parsing implementation."""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from tree_sitter import Tree, Node
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, ParserType, AICapability, AIContext, AIProcessingResult,
    InteractionType, ConfidenceLevel, ParserResult, PatternCategory, PatternPurpose
)
from parsers.models import FileClassification, BaseNodeDict
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorAudit, ErrorSeverity
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.request_cache import request_cache_context, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope
from utils.monitoring import operation_monitor

@dataclass
class TreeSitterParser(BaseParserInterface, AIParserInterface):
    """[4.1] Tree-sitter parser implementation with AI capabilities."""
    
    def __init__(self, language_id: str):
        """Initialize tree-sitter parser."""
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.TREE_SITTER,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.CODE_GENERATION,
                AICapability.CODE_MODIFICATION,
                AICapability.CODE_REVIEW,
                AICapability.LEARNING
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._parser = None
        self._language = None
        self._cache = None
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_parses": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "parse_times": []
        }
        self._warmup_complete = False
    
    async def initialize(self) -> bool:
        """Initialize the tree-sitter parser."""
        if self._initialized:
            return True
            
        try:
            # Update status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "starting"}
            )
            
            # Check if language is supported
            if self.language_id not in SupportedLanguage.__args__:
                raise ValueError(f"Language {self.language_id} not supported by tree-sitter-language-pack")
            
            # Initialize tree-sitter components
            self._parser = get_parser(self.language_id)
            self._language = get_language(self.language_id)
            
            if not self._parser or not self._language:
                raise ValueError(f"Failed to initialize parser/language for {self.language_id}")
            
            # Initialize cache
            self._cache = UnifiedCache(f"tree_sitter_parser_{self.language_id}")
            await cache_coordinator.register_cache(self._cache)
            
            # Initialize cache analytics
            analytics = await get_cache_analytics()
            analytics.register_warmup_function(
                f"tree_sitter_parser_{self.language_id}",
                self._warmup_cache
            )
            
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "language_loaded"}
            )
            
            # Register shutdown handler
            register_shutdown_handler(self.cleanup)
            
            self._initialized = True
            await log(f"Tree-sitter parser initialized for {self.language_id}", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.HEALTHY,
                details={
                    "stage": "complete",
                    "language": self.language_id
                }
            )
            
            return True
        except Exception as e:
            await log(f"Error initializing tree-sitter parser for {self.language_id}: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            return False
    
    async def _warmup_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for tree-sitter parser cache."""
        results = {}
        for key in keys:
            try:
                # Parse some sample code for this key
                sample_code = "// Sample code for warmup"
                tree = self._parser.parse(bytes(sample_code, "utf8"))
                if tree:
                    results[key] = {"root": tree.root_node}
            except Exception as e:
                await log(f"Error warming up cache for {key}: {e}", level="warning")
        return results
    
    @handle_async_errors(error_types=(ProcessingError,))
    async def parse(self, source_code: str) -> Optional[ParserResult]:
        """Parse source code using tree-sitter."""
        if not self._initialized:
            await self.initialize()
            
        async with AsyncErrorBoundary(
            operation_name=f"tree_sitter_parse_{self.language_id}",
            error_types=(ProcessingError,),
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Get request context for metrics
                request_cache = get_current_request_cache()
                if request_cache:
                    await request_cache.set(
                        "parse_count",
                        (await request_cache.get("parse_count", 0)) + 1
                    )
                
                # Use monitor_operation context manager
                with operation_monitor("parse", f"tree_sitter_{self.language_id}"):
                    tree = self._parser.parse(bytes(source_code, "utf8"))
                    
                # Create result with proper error handling
                result = ParserResult(
                    success=True,
                    ast={"root": tree.root_node},
                    source_code=source_code
                )
                
                return result
                
            except Exception as e:
                await ErrorAudit.record_error(
                    e,
                    f"tree_sitter_parse_{self.language_id}",
                    ProcessingError,
                    context={"source_size": len(source_code)}
                )
                return None
    
    async def cleanup(self):
        """Clean up tree-sitter parser resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up parser
            if self._parser:
                self._parser.reset()
                self._parser = None
            
            # Clean up language
            self._language = None
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(f"tree_sitter_parser_{self.language_id}")
                self._cache = None
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO parser_metrics (
                        timestamp, language_id, total_parses,
                        successful_parses, failed_parses,
                        cache_hits, cache_misses, avg_parse_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """, (
                    time.time(),
                    self.language_id,
                    self._metrics["total_parses"],
                    self._metrics["successful_parses"],
                    self._metrics["failed_parses"],
                    self._metrics["cache_hits"],
                    self._metrics["cache_misses"],
                    sum(self._metrics["parse_times"]) / len(self._metrics["parse_times"]) if self._metrics["parse_times"] else 0
                ))
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            self._pending_tasks.clear()
            
            self._initialized = False
            await log(f"Tree-sitter parser cleaned up for {self.language_id}", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up tree-sitter parser for {self.language_id}: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"tree_sitter_parser_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )

# Global instance cache
_parser_instances: Dict[str, TreeSitterParser] = {}

async def get_tree_sitter_parser(language_id: str) -> Optional[TreeSitterParser]:
    """[4.2] Get a tree-sitter parser instance for a language."""
    if language_id not in _parser_instances:
        parser = TreeSitterParser(language_id)
        if await parser.initialize():
            _parser_instances[language_id] = parser
        else:
            return None
    return _parser_instances[language_id] 