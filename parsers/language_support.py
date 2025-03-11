"""Language support management.

This module provides support level tracking for languages,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    SupportLevel, LanguageSupport as LanguageSupportType
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
class LanguageSupport(BaseParser):
    """Language support management.
    
    This class manages support levels for languages,
    integrating with the parser system for efficient support tracking.
    
    Attributes:
        language_id (str): The identifier for the language
        support (LanguageSupportType): The language support configuration
        level (SupportLevel): The current support level
        capabilities (Set[AICapability]): Set of supported AI capabilities
    """
    
    def __init__(self, language_id: str):
        """Initialize language support.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CONFIG,
            parser_type=ParserType.CUSTOM
        )
        self.support = LanguageSupportType()
        self.level = SupportLevel.EXPERIMENTAL
        self.capabilities = set()
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize language support.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"language_support_initialization_{self.language_id}"):
                # Load support through async_runner
                init_task = submit_async_task(self._load_support())
                await asyncio.wrap_future(init_task)
                
                if not self.support:
                    raise ProcessingError(f"Failed to load support for {self.language_id}")
                
                # Process support level and capabilities
                self.level = self.support.level
                self.capabilities = set(self.support.capabilities)
                
                await log(f"Language support initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing language support: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"language_support_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"language_support_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"support_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize language support for {self.language_id}: {e}")
    
    async def _load_support(self) -> None:
        """Load language support from storage."""
        try:
            async with transaction_scope() as txn:
                # Load support
                support_result = await txn.fetchrow("""
                    SELECT * FROM language_support
                    WHERE language_id = $1
                """, self.language_id)
                
                if support_result:
                    self.support = LanguageSupportType(**support_result)
                    
        except Exception as e:
            await log(f"Error loading support: {e}", level="error")
            raise ProcessingError(f"Failed to load support: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_support(self, support: Dict[str, Any]) -> bool:
        """Update language support.
        
        Args:
            support: The new support values
            
        Returns:
            bool: True if update was successful
        """
        try:
            async with AsyncErrorBoundary(f"support_update_{self.language_id}"):
                # Update through async_runner
                update_task = submit_async_task(self._update_support_in_db(support))
                await asyncio.wrap_future(update_task)
                
                # Update local support
                self.support.update(support)
                
                # Update level and capabilities
                self.level = self.support.level
                self.capabilities = set(self.support.capabilities)
                
                await log(f"Support updated for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating support: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"support_update_{self.language_id}",
                ProcessingError,
                context={"support": support}
            )
            return False
    
    async def _update_support_in_db(self, support: Dict[str, Any]) -> None:
        """Update support in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_support (language_id, support)
                VALUES ($1, $2)
                ON CONFLICT (language_id) DO UPDATE
                SET support = $2
            """, self.language_id, support)
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_level(self, level: SupportLevel) -> bool:
        """Update support level.
        
        Args:
            level: The new support level
            
        Returns:
            bool: True if update was successful
        """
        try:
            async with AsyncErrorBoundary(f"level_update_{self.language_id}"):
                # Update through async_runner
                update_task = submit_async_task(self._update_level_in_db(level))
                await asyncio.wrap_future(update_task)
                
                # Update local state
                self.level = level
                self.support.level = level
                
                await log(f"Support level updated to {level} for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating support level: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"level_update_{self.language_id}",
                ProcessingError,
                context={"level": level}
            )
            return False
    
    async def _update_level_in_db(self, level: SupportLevel) -> None:
        """Update support level in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                UPDATE language_support
                SET level = $1
                WHERE language_id = $2
            """, level.value, self.language_id)
    
    @handle_async_errors(error_types=ProcessingError)
    async def add_capability(self, capability: AICapability) -> bool:
        """Add an AI capability.
        
        Args:
            capability: The AI capability to add
            
        Returns:
            bool: True if addition was successful
        """
        try:
            async with AsyncErrorBoundary(f"capability_add_{self.language_id}"):
                if capability in self.capabilities:
                    return True
                
                # Update through async_runner
                update_task = submit_async_task(self._add_capability_in_db(capability))
                await asyncio.wrap_future(update_task)
                
                # Update local state
                self.capabilities.add(capability)
                self.support.capabilities.append(capability)
                
                await log(f"Capability {capability} added for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error adding capability: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"capability_add_{self.language_id}",
                ProcessingError,
                context={"capability": capability}
            )
            return False
    
    async def _add_capability_in_db(self, capability: AICapability) -> None:
        """Add capability in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                UPDATE language_support
                SET capabilities = array_append(capabilities, $1)
                WHERE language_id = $2
            """, capability.value, self.language_id)

# Global instance cache
_support_instances: Dict[str, LanguageSupport] = {}

async def get_language_support(language_id: str) -> Optional[LanguageSupport]:
    """Get a language support instance.
    
    Args:
        language_id: The language to get support for
        
    Returns:
        Optional[LanguageSupport]: The support instance or None if initialization fails
    """
    if language_id not in _support_instances:
        support = LanguageSupport(language_id)
        if await support.initialize():
            _support_instances[language_id] = support
        else:
            return None
    return _support_instances[language_id]

# Export public interfaces
__all__ = [
    'LanguageSupport',
    'get_language_support',
    'language_support'
] 