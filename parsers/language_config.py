"""Language configuration management.

This module provides configuration management for supported languages,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    LanguageConfig as LanguageConfigType,
    LanguageFeatures, LanguageSupport
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
from parsers.language_mapping import normalize_language_name

@dataclass
class LanguageConfig(BaseParser):
    """Language configuration management.
    
    This class manages language-specific configuration and features,
    integrating with the parser system for efficient configuration handling.
    
    Attributes:
        language_id (str): The identifier for the language
        config (LanguageConfigType): The language configuration
        features (LanguageFeatures): The language features
        support (LanguageSupport): The language support level
    """
    
    def __init__(self, language_id: str):
        """Initialize language configuration.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CONFIG,
            parser_type=ParserType.CUSTOM
        )
        self.config = LanguageConfigType()
        self.features = LanguageFeatures()
        self.support = LanguageSupport()
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize language configuration.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"language_config_initialization_{self.language_id}"):
                # Load configuration through async_runner
                init_task = submit_async_task(self._load_configuration())
                await asyncio.wrap_future(init_task)
                
                if not all([self.config, self.features, self.support]):
                    raise ProcessingError(f"Failed to load configuration for {self.language_id}")
                
                await log(f"Language configuration initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing language configuration: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"language_config_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"language_config_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"config_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize language configuration for {self.language_id}: {e}")
    
    async def _load_configuration(self) -> None:
        """Load language configuration from storage."""
        try:
            async with transaction_scope() as txn:
                # Load config
                config_result = await txn.fetchrow("""
                    SELECT * FROM language_configs
                    WHERE language_id = $1
                """, self.language_id)
                
                if config_result:
                    self.config = LanguageConfigType(**config_result)
                
                # Load features
                features_result = await txn.fetchrow("""
                    SELECT * FROM language_features
                    WHERE language_id = $1
                """, self.language_id)
                
                if features_result:
                    self.features = LanguageFeatures(**features_result)
                
                # Load support level
                support_result = await txn.fetchrow("""
                    SELECT * FROM language_support
                    WHERE language_id = $1
                """, self.language_id)
                
                if support_result:
                    self.support = LanguageSupport(**support_result)
                    
        except Exception as e:
            await log(f"Error loading configuration: {e}", level="error")
            raise ProcessingError(f"Failed to load configuration: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_configuration(self, config: Dict[str, Any]) -> bool:
        """Update language configuration.
        
        Args:
            config: The new configuration values
            
        Returns:
            bool: True if update was successful
        """
        try:
            async with AsyncErrorBoundary(f"config_update_{self.language_id}"):
                # Update through async_runner
                update_task = submit_async_task(self._update_config_in_db(config))
                await asyncio.wrap_future(update_task)
                
                # Update local config
                self.config.update(config)
                
                await log(f"Configuration updated for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating configuration: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"config_update_{self.language_id}",
                ProcessingError,
                context={"config": config}
            )
            return False
    
    async def _update_config_in_db(self, config: Dict[str, Any]) -> None:
        """Update configuration in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_configs (language_id, config)
                VALUES ($1, $2)
                ON CONFLICT (language_id) DO UPDATE
                SET config = $2
            """, self.language_id, config)
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_features(self, features: Dict[str, Any]) -> bool:
        """Update language features.
        
        Args:
            features: The new feature values
            
        Returns:
            bool: True if update was successful
        """
        try:
            async with AsyncErrorBoundary(f"features_update_{self.language_id}"):
                # Update through async_runner
                update_task = submit_async_task(self._update_features_in_db(features))
                await asyncio.wrap_future(update_task)
                
                # Update local features
                self.features.update(features)
                
                await log(f"Features updated for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating features: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"features_update_{self.language_id}",
                ProcessingError,
                context={"features": features}
            )
            return False
    
    async def _update_features_in_db(self, features: Dict[str, Any]) -> None:
        """Update features in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_features (language_id, features)
                VALUES ($1, $2)
                ON CONFLICT (language_id) DO UPDATE
                SET features = $2
            """, self.language_id, features)
    
    @handle_async_errors(error_types=ProcessingError)
    async def update_support(self, support: Dict[str, Any]) -> bool:
        """Update language support level.
        
        Args:
            support: The new support level values
            
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
                
                await log(f"Support level updated for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error updating support level: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"support_update_{self.language_id}",
                ProcessingError,
                context={"support": support}
            )
            return False
    
    async def _update_support_in_db(self, support: Dict[str, Any]) -> None:
        """Update support level in database."""
        async with transaction_scope() as txn:
            await txn.execute("""
                INSERT INTO language_support (language_id, support)
                VALUES ($1, $2)
                ON CONFLICT (language_id) DO UPDATE
                SET support = $2
            """, self.language_id, support)

# Global instance cache
_config_instances: Dict[str, LanguageConfig] = {}

async def get_language_config(language_id: str) -> Optional[LanguageConfig]:
    """Get a language configuration instance.
    
    Args:
        language_id: The language to get configuration for
        
    Returns:
        Optional[LanguageConfig]: The configuration instance or None if initialization fails
    """
    if language_id not in _config_instances:
        config = LanguageConfig(language_id)
        if await config.initialize():
            _config_instances[language_id] = config
        else:
            return None
    return _config_instances[language_id] 