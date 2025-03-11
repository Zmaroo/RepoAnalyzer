"""AI pattern processing management.

This module provides AI-powered pattern processing capabilities,
integrating with the parser system and AI tools infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    PatternCategory, PatternPurpose, PatternValidationResult
)
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
from db.transaction import transaction_scope

@dataclass
class AIPatternProcessor(BaseParser):
    """AI pattern processing management.
    
    This class manages AI-powered pattern processing,
    integrating with the parser system and AI tools.
    
    Attributes:
        language_id (str): The identifier for the language
        capabilities (Set[AICapability]): Set of supported AI capabilities
        _pattern_cache (UnifiedCache): Cache for AI-generated patterns
    """
    
    def __init__(self, language_id: str):
        """Initialize AI pattern processor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.capabilities = set()
        self._pattern_cache = None
        self._processing_stats = {
            "total_processed": 0,
            "successful_processing": 0,
            "failed_processing": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "processing_times": []
        }
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize AI pattern processor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"ai_pattern_processor_initialization_{self.language_id}"):
                # Initialize cache
                self._pattern_cache = UnifiedCache(f"ai_pattern_processor_{self.language_id}")
                await cache_coordinator.register_cache(
                    f"ai_pattern_processor_{self.language_id}",
                    self._pattern_cache
                )
                
                # Load capabilities through async_runner
                init_task = submit_async_task(self._load_capabilities())
                await asyncio.wrap_future(init_task)
                
                if not self.capabilities:
                    raise ProcessingError(f"Failed to load capabilities for {self.language_id}")
                
                # Initialize AI tools
                from ai_tools.ai_interface import AIAssistant
                self._ai_assistant = await AIAssistant.create()
                
                await log(f"AI pattern processor initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing AI pattern processor: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"ai_pattern_processor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"processor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize AI pattern processor for {self.language_id}: {e}")
    
    async def _load_capabilities(self) -> None:
        """Load supported AI capabilities from storage."""
        try:
            # Update health status
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "loading_capabilities"}
            )
            
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_capabilities_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load capabilities
                capabilities_result = await txn.fetch("""
                    SELECT capability FROM language_ai_capabilities
                    WHERE language_id = $1
                """, self.language_id)
                
                if capabilities_result:
                    self.capabilities = {AICapability(row["capability"]) for row in capabilities_result}
                
                # Record transaction metrics
                await txn.record_operation("load_capabilities_complete", {
                    "language_id": self.language_id,
                    "capabilities_count": len(self.capabilities),
                    "end_time": time.time()
                })
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    f"ai_pattern_processor_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "capabilities_loaded": bool(capabilities_result),
                        "capabilities_count": len(self.capabilities)
                    }
                )
                    
        except Exception as e:
            await log(f"Error loading capabilities: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"ai_pattern_processor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            raise ProcessingError(f"Failed to load capabilities: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def process_pattern(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process a pattern using AI capabilities.
        
        Args:
            pattern_name: The name of the pattern to process
            content: The content to process
            context: The AI processing context
            
        Returns:
            PatternValidationResult: The validation result
        """
        try:
            async with AsyncErrorBoundary(f"ai_pattern_processing_{self.language_id}"):
                # Check cache first
                cache_key = f"pattern:{self.language_id}:{pattern_name}:{hash(content)}"
                cached_result = await self._pattern_cache.get(cache_key)
                if cached_result:
                    self._processing_stats["cache_hits"] += 1
                    return PatternValidationResult(**cached_result)
                
                self._processing_stats["cache_misses"] += 1
                
                # Process through async_runner
                process_task = submit_async_task(
                    self._process_with_ai(pattern_name, content, context)
                )
                result = await asyncio.wrap_future(process_task)
                
                # Cache result
                await self._pattern_cache.set(cache_key, result.__dict__)
                
                # Update stats
                self._processing_stats["total_processed"] += 1
                self._processing_stats["successful_processing"] += 1
                
                await log(f"Pattern processed for {self.language_id}", level="info")
                return result
                
        except Exception as e:
            await log(f"Error processing pattern: {e}", level="error")
            self._processing_stats["failed_processing"] += 1
            await ErrorAudit.record_error(
                e,
                f"ai_pattern_processing_{self.language_id}",
                ProcessingError,
                context={
                    "pattern_name": pattern_name,
                    "content_size": len(content)
                }
            )
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _process_with_ai(
        self,
        pattern_name: str,
        content: str,
        context: AIContext
    ) -> PatternValidationResult:
        """Process pattern with AI assistance."""
        try:
            start_time = time.time()
            
            # Get AI response
            response = await self._ai_assistant.process_pattern(
                pattern_name,
                content,
                self.language_id,
                context
            )
            
            # Update timing stats
            processing_time = time.time() - start_time
            self._processing_stats["processing_times"].append(processing_time)
            
            return PatternValidationResult(
                is_valid=response.success,
                errors=response.errors if not response.success else [],
                validation_time=processing_time
            )
            
        except Exception as e:
            await log(f"Error in AI processing: {e}", level="error")
            return PatternValidationResult(
                is_valid=False,
                errors=[str(e)]
            )
    
    async def _cleanup(self) -> None:
        """Clean up AI pattern processor resources."""
        try:
            # Clean up cache
            if self._pattern_cache:
                await cache_coordinator.unregister_cache(f"ai_pattern_processor_{self.language_id}")
                self._pattern_cache = None
            
            # Save processing stats
            async with transaction_scope() as txn:
                await txn.execute("""
                    INSERT INTO ai_pattern_processor_stats (
                        timestamp, language_id,
                        total_processed, successful_processing,
                        failed_processing, avg_processing_time
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                """, (
                    time.time(),
                    self.language_id,
                    self._processing_stats["total_processed"],
                    self._processing_stats["successful_processing"],
                    self._processing_stats["failed_processing"],
                    sum(self._processing_stats["processing_times"]) / len(self._processing_stats["processing_times"])
                    if self._processing_stats["processing_times"] else 0
                ))
            
            await log(f"AI pattern processor cleaned up for {self.language_id}", level="info")
            
        except Exception as e:
            await log(f"Error cleaning up AI pattern processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup AI pattern processor: {e}")

# Global instance cache
_processor_instances: Dict[str, AIPatternProcessor] = {}

async def get_ai_pattern_processor(language_id: str) -> Optional[AIPatternProcessor]:
    """Get an AI pattern processor instance.
    
    Args:
        language_id: The language to get processor for
        
    Returns:
        Optional[AIPatternProcessor]: The processor instance or None if initialization fails
    """
    if language_id not in _processor_instances:
        processor = AIPatternProcessor(language_id)
        if await processor.initialize():
            _processor_instances[language_id] = processor
        else:
            return None
    return _processor_instances[language_id]

# Export public interfaces
__all__ = [
    'AIPatternProcessor',
    'get_ai_pattern_processor',
    'ai_pattern_processor'
] 