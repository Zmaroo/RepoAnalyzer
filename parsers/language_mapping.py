"""Language mapping management.

This module provides mapping between file extensions and languages,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from tree_sitter_language_pack import SupportedLanguage, get_language, get_parser
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    LanguageMapping as LanguageMappingType
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

def normalize_language_name(language_id: str) -> str:
    """Normalize a language identifier.
    
    Args:
        language_id: The language identifier to normalize
        
    Returns:
        str: The normalized language identifier
    """
    return language_id.lower().replace("-", "_").replace(" ", "_")

@dataclass
class LanguageMapping(BaseParser):
    """Language mapping management.
    
    This class manages mappings between file extensions and languages,
    integrating with the parser system for efficient mapping handling.
    
    Attributes:
        language_id (str): The identifier for the language
        mapping (LanguageMappingType): The language mapping configuration
        extensions (Set[str]): Set of file extensions for this language
        patterns (List[str]): List of filename patterns for this language
    """
    
    def __init__(self, language_id: str):
        """Initialize language mapping.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CONFIG,
            parser_type=ParserType.CUSTOM
        )
        self.mapping = LanguageMappingType()
        self.extensions = set()
        self.patterns = []
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize language mapping.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"language_mapping_initialization_{self.language_id}"):
                # Load mapping through async_runner
                init_task = submit_async_task(self._load_mapping())
                await asyncio.wrap_future(init_task)
                
                if not self.mapping:
                    raise ProcessingError(f"Failed to load mapping for {self.language_id}")
                
                # Process extensions and patterns
                self.extensions = set(self.mapping.extensions)
                self.patterns = self.mapping.patterns
                
                await log(f"Language mapping initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing language mapping: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"language_mapping_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"language_mapping_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"mapping_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize language mapping for {self.language_id}: {e}")
    
    async def _load_mapping(self) -> None:
        """Load language mapping from storage."""
        try:
            async with transaction_scope() as txn:
                # Load mapping
                mapping_result = await txn.fetchrow("""
                    SELECT * FROM language_mappings
                    WHERE language_id = $1
                """, self.language_id)
                
                if mapping_result:
                    self.mapping = LanguageMappingType(**mapping_result)
                    
        except Exception as e:
            await log(f"Error loading mapping: {e}", level="error")
            raise ProcessingError(f"Failed to load mapping: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_mapping(self, mapping: Dict[str, Any]) -> bool:
        """Update language mapping.
        
        Args:
            mapping: The new mapping values
            
        Returns:
            bool: True if update was successful
        """
        try:
            async with AsyncErrorBoundary(f"mapping_update_{self.language_id}"):
                # Update through async_runner
                update_task = submit_async_task(self._update_mapping_in_db(mapping))
                await asyncio.wrap_future(update_task)
                
                # Update local mapping
                self.mapping.update(mapping)
                
                # Update extensions and patterns
                self.extensions = set(self.mapping.extensions)
                self.patterns = self.mapping.patterns
                
                await log(f"Mapping updated for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating mapping: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"mapping_update_{self.language_id}",
                ProcessingError,
                context={"mapping": mapping}
            )
            return False
    
    async def _update_mapping_in_db(self, mapping: Dict[str, Any]) -> None:
        """Update mapping in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_mappings (language_id, mapping)
                VALUES ($1, $2)
                ON CONFLICT (language_id) DO UPDATE
                SET mapping = $2
            """, self.language_id, mapping)
    
    @handle_async_errors(error_types=ProcessingError)
    async def add_extension(self, extension: str) -> bool:
        """Add a file extension mapping.
        
        Args:
            extension: The file extension to add
            
        Returns:
            bool: True if addition was successful
        """
        try:
            async with AsyncErrorBoundary(f"extension_add_{self.language_id}"):
                if extension in self.extensions:
                    return True
                
                # Update through async_runner
                update_task = submit_async_task(self._add_extension_in_db(extension))
                await asyncio.wrap_future(update_task)
                
                # Update local state
                self.extensions.add(extension)
                self.mapping.extensions.append(extension)
                
                await log(f"Extension {extension} added for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error adding extension: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"extension_add_{self.language_id}",
                ProcessingError,
                context={"extension": extension}
            )
            return False
    
    async def _add_extension_in_db(self, extension: str) -> None:
        """Add extension in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                UPDATE language_mappings
                SET extensions = array_append(extensions, $1)
                WHERE language_id = $2
            """, extension, self.language_id)
    
    @handle_async_errors(error_types=ProcessingError)
    async def add_pattern(self, pattern: str) -> bool:
        """Add a filename pattern mapping.
        
        Args:
            pattern: The filename pattern to add
            
        Returns:
            bool: True if addition was successful
        """
        try:
            async with AsyncErrorBoundary(f"pattern_add_{self.language_id}"):
                if pattern in self.patterns:
                    return True
                
                # Update through async_runner
                update_task = submit_async_task(self._add_pattern_in_db(pattern))
                await asyncio.wrap_future(update_task)
                
                # Update local state
                self.patterns.append(pattern)
                self.mapping.patterns.append(pattern)
                
                await log(f"Pattern {pattern} added for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error adding pattern: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"pattern_add_{self.language_id}",
                ProcessingError,
                context={"pattern": pattern}
            )
            return False
    
    async def _add_pattern_in_db(self, pattern: str) -> None:
        """Add pattern in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                UPDATE language_mappings
                SET patterns = array_append(patterns, $1)
                WHERE language_id = $2
            """, pattern, self.language_id)

# Global instance cache
_mapping_instances: Dict[str, LanguageMapping] = {}

async def get_language_mapping(language_id: str) -> Optional[LanguageMapping]:
    """Get a language mapping instance.
    
    Args:
        language_id: The language to get mapping for
        
    Returns:
        Optional[LanguageMapping]: The mapping instance or None if initialization fails
    """
    if language_id not in _mapping_instances:
        mapping = LanguageMapping(language_id)
        if await mapping.initialize():
            _mapping_instances[language_id] = mapping
        else:
            return None
    return _mapping_instances[language_id]
