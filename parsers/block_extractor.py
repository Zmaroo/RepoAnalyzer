"""Block extraction management.

This module provides block extraction capabilities for code analysis,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from parsers.types import (
    FileType, FeatureCategory, ParserType, Documentation, ComplexityMetrics,
    ExtractedFeatures, PatternCategory, PatternPurpose,
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel,
    ParserResult, PatternValidationResult, BlockType, BlockValidationResult,
    ExtractedBlock
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.base_parser import BaseParser
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
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope

@dataclass
class BlockExtractor(BaseParser):
    """Block extraction management.
    
    This class manages code block extraction,
    integrating with the parser system for efficient block handling.
    
    Attributes:
        language_id (str): The identifier for the language
        block_types (Set[BlockType]): Set of supported block types
        _blocks_cache (UnifiedCache): Cache for extracted blocks
    """
    
    def __init__(self, language_id: str):
        """Initialize block extractor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.block_types = set()
        self._blocks_cache = None
        self._extraction_stats = {
            "total_extractions": 0,
            "successful_extractions": 0,
            "failed_extractions": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "extraction_times": []
        }
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize block extractor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"block_extractor_initialization_{self.language_id}"):
                # Initialize cache
                self._blocks_cache = UnifiedCache(f"block_extractor_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"block_extractor_{self.language_id}",
                    self._blocks_cache
                )
                
                # Load block types through async_runner
                init_task = submit_async_task(self._load_block_types())
                await asyncio.wrap_future(init_task)
                
                if not self.block_types:
                    raise ProcessingError(f"Failed to load block types for {self.language_id}")
                
                await log(f"Block extractor initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing block extractor: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"block_extractor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"block_extractor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"extractor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize block extractor for {self.language_id}: {e}")
    
    async def _load_block_types(self) -> None:
        """Load supported block types from storage."""
        try:
            # Update health status
            await global_health_monitor.update_component_status(
                f"block_extractor_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "loading_block_types"}
            )
            
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_block_types_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load block types
                block_types_result = await txn.fetch("""
                    SELECT block_type FROM language_block_types
                    WHERE language_id = $1
                """, self.language_id)
                
                if block_types_result:
                    self.block_types = {BlockType(row["block_type"]) for row in block_types_result}
                
                # Record transaction metrics
                await txn.record_operation("load_block_types_complete", {
                    "language_id": self.language_id,
                    "block_types_count": len(self.block_types),
                    "end_time": time.time()
                })
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    f"block_extractor_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "block_types_loaded": bool(block_types_result),
                        "block_types_count": len(self.block_types)
                    }
                )
                    
        except Exception as e:
            await log(f"Error loading block types: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"block_extractor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            raise ProcessingError(f"Failed to load block types: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def extract_blocks(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract code blocks from AST.
        
        Args:
            ast: The AST to extract blocks from
            source_code: The original source code
            
        Returns:
            List[Dict[str, Any]]: The extracted blocks
        """
        try:
            async with AsyncErrorBoundary(f"block_extraction_{self.language_id}"):
                # Check cache first
                cache_key = f"blocks:{self.language_id}:{hash(source_code)}"
                cached_blocks = await self._blocks_cache.get(cache_key)
                if cached_blocks:
                    self._extraction_stats["cache_hits"] += 1
                    return cached_blocks
                
                self._extraction_stats["cache_misses"] += 1
                
                # Extract blocks through async_runner
                extract_task = submit_async_task(self._extract_all_blocks(ast, source_code))
                blocks = await asyncio.wrap_future(extract_task)
                
                # Cache blocks
                await self._blocks_cache.set(cache_key, blocks)
                
                # Update stats
                self._extraction_stats["total_extractions"] += 1
                self._extraction_stats["successful_extractions"] += 1
                
                await log(f"Blocks extracted for {self.language_id}", level="info")
                return blocks
                
        except Exception as e:
            await log(f"Error extracting blocks: {e}", level="error")
            self._extraction_stats["failed_extractions"] += 1
            await ErrorAudit.record_error(
                e,
                f"block_extraction_{self.language_id}",
                ProcessingError,
                context={"ast_size": len(str(ast))}
            )
            return []
    
    async def _extract_all_blocks(self, ast: Dict[str, Any], source_code: str) -> List[Dict[str, Any]]:
        """Extract all blocks from AST."""
        blocks = []
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            for block_type in self.block_types:
                # Get patterns for block type
                patterns = await pattern_processor.get_patterns_for_block_type(
                    block_type,
                    self.language_id
                )
                
                if patterns:
                    for pattern in patterns:
                        start_time = time.time()
                        try:
                            # Process pattern
                            processed = await pattern_processor.process_pattern(
                                pattern["name"],
                                ast,
                                self.language_id
                            )
                            
                            extraction_time = time.time() - start_time
                            self._extraction_stats["extraction_times"].append(extraction_time)
                            
                            if processed.matches:
                                for match in processed.matches:
                                    block = {
                                        "type": block_type.value,
                                        "start": match.get("start", 0),
                                        "end": match.get("end", 0),
                                        "content": source_code[match.get("start", 0):match.get("end", 0)],
                                        "metadata": match.get("metadata", {})
                                    }
                                    blocks.append(block)
                                
                        except Exception as e:
                            await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                            continue
                            
        except Exception as e:
            await log(f"Error extracting blocks: {e}", level="error")
            
        return blocks
    
    @handle_async_errors(error_types=ProcessingError)
    async def validate_block(self, block: Dict[str, Any]) -> BlockValidationResult:
        """Validate a code block.
        
        Args:
            block: The block to validate
            
        Returns:
            BlockValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"block_validation_{self.language_id}"):
                # Validate through async_runner
                validate_task = submit_async_task(self._validate_block_content(block))
                result = await asyncio.wrap_future(validate_task)
                
                await log(f"Block validated for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error validating block: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"block_validation_{self.language_id}",
                ProcessingError,
                context={"block_type": block.get("type")}
            )
            return BlockValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _validate_block_content(self, block: Dict[str, Any]) -> BlockValidationResult:
        """Validate block content."""
        errors = []
        
        # Check required fields
        required_fields = ["type", "start", "end", "content"]
        for field in required_fields:
            if field not in block:
                errors.append(f"Missing required field: {field}")
        
        # Check block type
        if "type" in block and BlockType(block["type"]) not in self.block_types:
            errors.append(f"Unsupported block type: {block['type']}")
        
        # Check content boundaries
        if "start" in block and "end" in block and "content" in block:
            if block["end"] <= block["start"]:
                errors.append("Invalid block boundaries")
            if len(block["content"]) != block["end"] - block["start"]:
                errors.append("Content length does not match boundaries")
        
        return BlockValidationResult(
            is_valid=len(errors) == 0,
            errors=errors
        )
    
    async def _cleanup(self) -> None:
        """Clean up block extractor resources."""
        try:
            # Clean up cache
            if self._blocks_cache:
                await cache_coordinator.unregister_cache(f"block_extractor_{self.language_id}")
                self._blocks_cache = None
            
            # Save extraction stats
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO block_extractor_stats (
                        timestamp, language_id,
                        total_extractions, successful_extractions,
                        failed_extractions, avg_extraction_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._extraction_stats["total_extractions"],
                    self._extraction_stats["successful_extractions"],
                    self._extraction_stats["failed_extractions"],
                    sum(self._extraction_stats["extraction_times"]) / len(self._extraction_stats["extraction_times"])
                    if self._extraction_stats["extraction_times"] else 0
                ))
            
            await log(f"Block extractor cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up block extractor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup block extractor: {e}")

# Global instance cache
_extractor_instances: Dict[str, BlockExtractor] = {}

async def get_block_extractor(language_id: str) -> Optional[BlockExtractor]:
    """Get a block extractor instance.
    
    Args:
        language_id: The language to get extractor for
        
    Returns:
        Optional[BlockExtractor]: The extractor instance or None if initialization fails
    """
    if language_id not in _extractor_instances:
        extractor = BlockExtractor(language_id)
        if await extractor.initialize():
            _extractor_instances[language_id] = extractor
        else:
            return None
    return _extractor_instances[language_id]

# Export public interfaces
__all__ = [
    'ExtractedBlock',
    'BlockExtractor',
    'get_block_extractor',
    'block_extractor'
] 