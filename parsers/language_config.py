"""Language configuration utilities for RepoAnalyzer.

This module provides utilities for managing language-specific configuration,
including parser settings, file types, and AI capabilities.
"""

from typing import Dict, Any, List, Optional, Union, Set
import asyncio
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
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks

class LanguageConfig:
    """Language configuration manager."""
    
    def __init__(self):
        """Initialize language configuration."""
        self._initialized = False
        self._cache = None
        register_shutdown_handler(self.cleanup)
    
    async def ensure_initialized(self):
        """Ensure the language configuration is initialized."""
        if not self._initialized:
            raise ProcessingError("Language configuration not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'LanguageConfig':
        """Create and initialize a language configuration instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("language_config_initialization"):
                # Initialize health monitoring first
                await global_health_monitor.update_component_status(
                    "language_config",
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )
                
                # Initialize cache
                instance._cache = UnifiedCache("language_config")
                await cache_coordinator.register_cache(instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log("Language configuration initialized", level="info")
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    "language_config",
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )
                
                return instance
        except Exception as e:
            await log(f"Error initializing language configuration: {e}", level="error")
            await global_health_monitor.update_component_status(
                "language_config",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"initialization_error": str(e)}
            )
            # Cleanup on initialization failure
            cleanup_task = submit_async_task(instance.cleanup())
            await asyncio.wrap_future(cleanup_task)
            raise ProcessingError(f"Failed to initialize language configuration: {e}")
    
    async def get_language_config(self, language_id: str) -> Dict[str, Any]:
        """Get configuration for a language."""
        if not self._initialized:
            await self.ensure_initialized()
        
        # Check cache first
        cache_key = f"language_config:{language_id}"
        cached_config = await self._cache.get(cache_key)
        if cached_config:
            return cached_config
        
        # Normalize language ID
        normalized = normalize_language_name(language_id)
        
        # Get configuration based on parser type
        if normalized in CUSTOM_PARSER_CLASSES:
            config = await self._get_custom_parser_config(normalized)
        elif normalized in SupportedLanguage.__args__:
            config = await self._get_tree_sitter_config(normalized)
        else:
            config = {
                "language_id": normalized,
                "parser_type": ParserType.UNKNOWN.value,
                "file_type": FileType.UNKNOWN.value,
                "capabilities": []
            }
        
        # Cache configuration
        await self._cache.set(cache_key, config)
        
        return config
    
    async def _get_custom_parser_config(self, language_id: str) -> Dict[str, Any]:
        """Get configuration for a custom parser."""
        parser_class = CUSTOM_PARSER_CLASSES[language_id]
        
        # Get default file type
        file_type = FileType.CODE
        if hasattr(parser_class, 'DEFAULT_FILE_TYPE'):
            file_type = parser_class.DEFAULT_FILE_TYPE
        
        # Get AI capabilities
        capabilities = {
            AICapability.CODE_UNDERSTANDING,
            AICapability.CODE_GENERATION,
            AICapability.CODE_MODIFICATION,
            AICapability.CODE_REVIEW,
            AICapability.DOCUMENTATION,
            AICapability.LEARNING
        }
        if hasattr(parser_class, 'AI_CAPABILITIES'):
            capabilities = parser_class.AI_CAPABILITIES
        
        return {
            "language_id": language_id,
            "parser_type": ParserType.CUSTOM.value,
            "file_type": file_type.value,
            "capabilities": [c.value for c in capabilities],
            "custom_parser_class": parser_class.__name__
        }
    
    async def _get_tree_sitter_config(self, language_id: str) -> Dict[str, Any]:
        """Get configuration for a tree-sitter parser."""
        try:
            # Test if we can get a parser for this language
            parser = get_parser(language_id)
            binding = get_binding(language_id)
            lang = get_language(language_id)
            
            return {
                "language_id": language_id,
                "parser_type": ParserType.TREE_SITTER.value,
                "file_type": FileType.CODE.value,
                "capabilities": [
                    AICapability.CODE_UNDERSTANDING.value,
                    AICapability.CODE_GENERATION.value,
                    AICapability.CODE_MODIFICATION.value,
                    AICapability.CODE_REVIEW.value,
                    AICapability.DOCUMENTATION.value
                ],
                "has_parser": parser is not None,
                "has_binding": binding is not None,
                "has_language": lang is not None
            }
        except Exception as e:
            await log(f"Error getting tree-sitter config for {language_id}: {e}", level="error")
            return {
                "language_id": language_id,
                "parser_type": ParserType.TREE_SITTER.value,
                "file_type": FileType.CODE.value,
                "capabilities": [AICapability.CODE_UNDERSTANDING.value],
                "has_parser": False,
                "has_binding": False,
                "has_language": False,
                "error": str(e)
            }
    
    async def cleanup(self):
        """Clean up language configuration resources."""
        try:
            if not self._initialized:
                return
                
            # Update status
            await global_health_monitor.update_component_status(
                "language_config",
                ComponentStatus.SHUTTING_DOWN,
                details={"stage": "starting"}
            )
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache("language_config")
                self._cache = None
            
            # Let async_runner handle remaining tasks
            cleanup_tasks()
            
            self._initialized = False
            await log("Language configuration cleaned up", level="info")
            
            # Update final status
            await global_health_monitor.update_component_status(
                "language_config",
                ComponentStatus.SHUTDOWN,
                details={"cleanup": "successful"}
            )
        except Exception as e:
            await log(f"Error cleaning up language configuration: {e}", level="error")
            await global_health_monitor.update_component_status(
                "language_config",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"cleanup_error": str(e)}
            )
            raise ProcessingError(f"Failed to cleanup language configuration: {e}")

# Create singleton instance
language_config = None

async def get_language_config() -> LanguageConfig:
    """Get or create the language configuration singleton instance."""
    global language_config
    if language_config is None:
        language_config = await LanguageConfig.create()
    return language_config

# Export public interfaces
__all__ = [
    'LanguageConfig',
    'get_language_config',
    'language_config'
] 