"""Block extraction utilities for RepoAnalyzer.

This module provides utilities for extracting code blocks from source code using
tree-sitter. It handles extraction of functions, classes, and other code blocks.
Integrates with cache analytics, error handling, and logging systems.
"""

from typing import Dict, Any, List, Optional, Union, Set, Tuple
import asyncio
from dataclasses import dataclass, field
import time
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.language_mapping import normalize_language_name
from parsers.custom_parsers import CUSTOM_PARSER_CLASSES
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
from utils.request_cache import request_cache_context, cached_in_request, get_current_request_cache
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope

@dataclass
class ExtractedBlock:
    """Extracted code block."""
    content: str
    start_line: int
    end_line: int
    block_type: str
    name: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

class BlockExtractor:
    """Block extractor that handles code block extraction."""
    
    def __init__(self):
        """Initialize block extractor."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._metrics = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "extraction_times": []
        }
        self._warmup_complete = False
        
        # Initialize caches
        self._block_cache = UnifiedCache("block_extractor_blocks")
        self._child_cache = UnifiedCache("block_extractor_children")
        
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the block extractor is initialized."""
        if not self._initialized:
            raise ProcessingError("Block extractor not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'BlockExtractor':
        """Create and initialize a block extractor instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("block_extractor_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "block_extractor",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Register caches with coordinator
                await cache_coordinator.register_cache("block_extractor_blocks", instance._block_cache)
                await cache_coordinator.register_cache("block_extractor_children", instance._child_cache)
                
                # Initialize cache analytics
                analytics = await get_cache_analytics()
                analytics.register_warmup_function(
                    "block_extractor_blocks",
                    instance._warmup_block_cache
                )
                analytics.register_warmup_function(
                    "block_extractor_children",
                    instance._warmup_child_cache
                )
                
                instance._initialized = True
                await log("Block extractor initialized", level="info")
                
                # Update final status
                await global_health_monitor.update_component_status(
                    "block_extractor",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing block extractor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "block_extractor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize block extractor: {e}")

    async def _warmup_block_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for block cache."""
        results = {}
        for key in keys:
            try:
                # Extract a sample block for warmup
                sample_code = "def sample_function():\n    pass"
                block = await self.extract_block("python", sample_code, None)
                if block:
                    results[key] = block.__dict__
            except Exception as e:
                await log(f"Error warming up block cache for {key}: {e}", level="warning")
        return results

    async def _warmup_child_cache(self, keys: List[str]) -> Dict[str, Any]:
        """Warmup function for child blocks cache."""
        results = {}
        for key in keys:
            try:
                # Extract sample child blocks for warmup
                sample_code = "class Sample:\n    def method(self):\n        pass"
                blocks = await self.get_child_blocks("python", sample_code, None)
                if blocks:
                    results[key] = [block.__dict__ for block in blocks]
            except Exception as e:
                await log(f"Error warming up child cache for {key}: {e}", level="warning")
        return results

    @handle_async_errors(error_types=ProcessingError)
    @cached_in_request
    async def extract_block(self, language_id: str, source_code: str, node: Any) -> Optional[ExtractedBlock]:
        """Extract a code block from source code."""
        if not self._initialized:
            await self.ensure_initialized()
            
        start_time = time.time()
        self._metrics["total_extractions"] += 1
        
        # Get request context for metrics
        request_cache = get_current_request_cache()
        if request_cache:
            await request_cache.set(
                "extraction_count",
                (await request_cache.get("extraction_count", 0)) + 1
            )
        
        try:
            async with request_cache_context() as cache:
                # Check cache first
                cache_key = f"block:{language_id}:{hash(source_code)}:{hash(str(node))}"
                cached_block = await self._block_cache.get_async(cache_key)
                if cached_block:
                    self._metrics["cache_hits"] += 1
                    if request_cache:
                        await request_cache.set(
                            "extraction_cache_hits",
                            (await request_cache.get("extraction_cache_hits", 0)) + 1
                        )
                    return ExtractedBlock(**cached_block)
                
                self._metrics["cache_misses"] += 1
                
                # Get block content and metadata
                with monitor_operation("extract_block", "block_extractor"):
                    content, metadata = await self._get_block_content(language_id, source_code, node)
                if not content:
                    self._metrics["failed_extractions"] += 1
                    return None
                
                # Create block
                block = ExtractedBlock(
                    content=content,
                    start_line=node.start_point[0],
                    end_line=node.end_point[0],
                    block_type=node.type,
                    name=await self._get_block_name(node),
                    metadata=metadata
                )
                
                # Cache block
                await self._block_cache.set_async(cache_key, block.__dict__)
                
                # Update metrics
                self._metrics["successful_extractions"] += 1
                extraction_time = time.time() - start_time
                self._metrics["extraction_times"].append(extraction_time)
                
                # Track request-level metrics
                if request_cache:
                    extraction_metrics = {
                        "language_id": language_id,
                        "block_type": node.type,
                        "extraction_time": extraction_time,
                        "timestamp": time.time()
                    }
                    await request_cache.set(
                        f"extraction_metrics_{language_id}_{node.type}",
                        extraction_metrics
                    )
                
                return block
        except Exception as e:
            self._metrics["failed_extractions"] += 1
            extraction_time = time.time() - start_time
            
            # Track error in request context
            if request_cache:
                await request_cache.set(
                    "last_extraction_error",
                    {
                        "error": str(e),
                        "language_id": language_id,
                        "block_type": node.type if node else None,
                        "timestamp": time.time()
                    }
                )
            
            await log(f"Error extracting block: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "block_extraction",
                ProcessingError,
                context={
                    "language_id": language_id,
                    "block_type": node.type if node else None,
                    "extraction_time": extraction_time
                }
            )
            return None
    
    @handle_async_errors(error_types=ProcessingError)
    @cached_in_request
    async def get_child_blocks(self, language_id: str, source_code: str, parent_node: Any) -> List[ExtractedBlock]:
        """Get child blocks from a parent node."""
        if not self._initialized:
            await self.ensure_initialized()
            
        try:
            async with request_cache_context() as cache:
                # Check cache first
                cache_key = f"children:{language_id}:{hash(source_code)}:{hash(str(parent_node))}"
                cached_blocks = await self._child_cache.get_async(cache_key)
                if cached_blocks:
                    return [ExtractedBlock(**block) for block in cached_blocks]
                
                blocks = []
                with monitor_operation("get_child_blocks", "block_extractor"):
                    for child in parent_node.children:
                        if child.type in ['function', 'class', 'method', 'struct', 'enum']:
                            block = await self.extract_block(language_id, source_code, child)
                            if block:
                                blocks.append(block)
                
                # Cache blocks
                await self._child_cache.set_async(cache_key, [block.__dict__ for block in blocks])
                
                return blocks
        except Exception as e:
            await log(f"Error getting child blocks: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "child_block_extraction",
                ProcessingError,
                context={
                    "language_id": language_id,
                    "parent_type": parent_node.type if parent_node else None
                }
            )
            return []
    
    async def _get_block_content(self, language_id: str, source_code: str, node: Any) -> Tuple[Optional[str], Dict[str, Any]]:
        """Get block content and metadata."""
        try:
            # Get content from source code
            lines = source_code.splitlines()
            start_line = node.start_point[0]
            end_line = node.end_point[0]
            
            if start_line >= len(lines) or end_line >= len(lines):
                return None, {}
            
            content = '\n'.join(lines[start_line:end_line + 1])
            
            # Get metadata
            metadata = {
                'language': language_id,
                'type': node.type,
                'start_byte': node.start_byte,
                'end_byte': node.end_byte,
                'start_point': node.start_point,
                'end_point': node.end_point,
                'is_named': node.is_named,
                'has_error': node.has_error,
                'child_count': len(node.children)
            }
            
            return content, metadata
        except Exception as e:
            await log(f"Error getting block content: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "block_content_extraction",
                ProcessingError,
                context={
                    "language_id": language_id,
                    "node_type": node.type if node else None
                }
            )
            return None, {}
    
    async def _get_block_name(self, node: Any) -> Optional[str]:
        """Get block name from node."""
        try:
            # Check for identifier child
            for child in node.children:
                if child.type == 'identifier':
                    return child.text.decode('utf8')
            return None
        except Exception as e:
            await log(f"Error getting block name: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "block_name_extraction",
                ProcessingError,
                context={"node_type": node.type if node else None}
            )
            return None
    
    async def cleanup(self):
        """Clean up block extractor resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "block_extractor",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up caches
            await cache_coordinator.unregister_cache("block_extractor_blocks")
            await cache_coordinator.unregister_cache("block_extractor_children")
            
            # Save error audit report
            await ErrorAudit.save_report()
            
            # Save metrics to database
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO block_extractor_metrics (
                        timestamp, total_extractions,
                        successful_extractions, failed_extractions,
                        cache_hits, cache_misses, avg_extraction_time
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """, (
                    time.time(),
                    self._metrics["total_extractions"],
                    self._metrics["successful_extractions"],
                    self._metrics["failed_extractions"],
                    self._metrics["cache_hits"],
                    self._metrics["cache_misses"],
                    sum(self._metrics["extraction_times"]) / len(self._metrics["extraction_times"]) if self._metrics["extraction_times"] else 0
                ))
            
            # Clean up any remaining tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            await log("Block extractor cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "block_extractor",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up block extractor: {e}", level="error")
            await global_health_monitor.update_component_status(
                "block_extractor",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup block extractor: {e}")

# Global instance
block_extractor = None

async def get_block_extractor() -> BlockExtractor:
    """Get or create the block extractor singleton instance."""
    global block_extractor
    if block_extractor is None:
        block_extractor = await BlockExtractor.create()
    return block_extractor

# Export public interfaces
__all__ = [
    'ExtractedBlock',
    'BlockExtractor',
    'get_block_extractor',
    'block_extractor'
] 