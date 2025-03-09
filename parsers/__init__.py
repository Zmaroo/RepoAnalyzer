"""Parser system for RepoAnalyzer.

This module provides a unified interface for parsing source code using either
tree-sitter-language-pack or custom parsers, depending on availability and precedence.

Core Components:
1. UnifiedParser - Main entry point for parsing source code
2. TreeSitterParser - Tree-sitter based parser implementation
3. CustomParser - Custom parser implementation
4. PatternProcessor - Handles pattern matching and feature extraction
"""

from typing import Dict, Any, List, Optional, Union, Tuple, Set
import asyncio
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
from parsers.parser_interfaces import BaseParser, TreeSitterParser, CustomParser
from parsers.unified_parser import UnifiedParser, get_unified_parser
from parsers.pattern_processor import PatternProcessor, get_pattern_processor
from parsers.feature_extractor import BaseFeatureExtractor, TreeSitterFeatureExtractor, CustomFeatureExtractor
from parsers.language_config import LanguageConfig, get_language_config
from parsers.language_support import LanguageSupport, get_language_support
from parsers.file_classification import FileClassifier, get_file_classifier
from parsers.block_extractor import BlockExtractor, get_block_extractor
from parsers.ai_pattern_processor import AIPatternProcessor, get_ai_pattern_processor
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope

async def initialize_parser_system() -> bool:
    """Initialize the parser system with proper dependency management."""
    try:
        # Initialize components in order with health monitoring
        components = [
            ("language_config", get_language_config),
            ("language_support", get_language_support),
            ("file_classifier", get_file_classifier),
            ("block_extractor", get_block_extractor),
            ("pattern_processor", get_pattern_processor),
            ("ai_pattern_processor", get_ai_pattern_processor),
            ("unified_parser", get_unified_parser)
        ]
        
        for name, get_component in components:
            try:
                await global_health_monitor.update_component_status(
                    "parser_system",
                    ComponentStatus.INITIALIZING,
                    details={"stage": f"initializing_{name}"}
                )
                
                component = await get_component()
                if not component:
                    raise ProcessingError(f"Failed to initialize {name}")
                
                # Register shutdown handler for each component
                register_shutdown_handler(component.cleanup)
                
                await log(f"{name} initialized", level="info")
                
            except Exception as e:
                await log(f"Error initializing {name}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "parser_system",
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={
                        "stage": f"initializing_{name}",
                        "error": str(e)
                    }
                )
                return False
        
        # Initialize cache analytics
        analytics = await get_cache_analytics()
        await analytics.start_monitoring()
        
        return True
        
    except Exception as e:
        await log(f"Error initializing parser system: {e}", level="error")
        return False

async def cleanup_parser_system():
    """Clean up parser system resources."""
    try:
        # Update status
        await global_health_monitor.update_component_status(
            "parser_system",
            ComponentStatus.SHUTTING_DOWN,
            details={"stage": "starting"}
        )
        
        # Clean up components in reverse order
        components = [
            ("unified_parser", get_unified_parser),
            ("ai_pattern_processor", get_ai_pattern_processor),
            ("pattern_processor", get_pattern_processor),
            ("block_extractor", get_block_extractor),
            ("file_classifier", get_file_classifier),
            ("language_support", get_language_support),
            ("language_config", get_language_config)
        ]
        
        for name, get_component in components:
            try:
                await global_health_monitor.update_component_status(
                    "parser_system",
                    ComponentStatus.SHUTTING_DOWN,
                    details={"stage": f"cleaning_up_{name}"}
                )
                
                component = await get_component()
                if component:
                    await component.cleanup()
                    await log(f"{name} cleaned up", level="info")
                    
            except Exception as e:
                await log(f"Error cleaning up {name}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    "parser_system",
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={
                        "stage": f"cleaning_up_{name}",
                        "error": str(e)
                    }
                )
        
        # Stop cache analytics
        analytics = await get_cache_analytics()
        await analytics.stop_monitoring()
        
        # Update final status
        await global_health_monitor.update_component_status(
            "parser_system",
            ComponentStatus.SHUTDOWN,
            details={"cleanup": "successful"}
        )
    except Exception as e:
        await log(f"Error cleaning up parser system: {e}", level="error")
        await global_health_monitor.update_component_status(
            "parser_system",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"cleanup_error": str(e)}
        )
        raise ProcessingError(f"Failed to cleanup parser system: {e}")

async def parse_source_code(source_code: str, language_id: str, file_type: FileType) -> Dict[str, Any]:
    """Parse source code using the unified parser."""
    try:
        async with request_cache_context() as cache:
            # Get unified parser instance
            unified_parser = await get_unified_parser()
            
            # Parse source code
            result = await unified_parser.parse(source_code, language_id, file_type)
            
            # Store parse result in request cache
            await cache.set(
                f"parse_result_{language_id}",
                {
                    "language_id": language_id,
                    "file_type": file_type.value,
                    "timestamp": time.time(),
                    "result": result
                }
            )
            
            return result
    except Exception as e:
        await log(f"Error parsing source code: {e}", level="error")
        return {}

# Export public interfaces
__all__ = [
    'initialize_parser_system',
    'cleanup_parser_system',
    'parse_source_code',
    'UnifiedParser',
    'TreeSitterParser',
    'CustomParser',
    'PatternProcessor',
    'BaseFeatureExtractor',
    'TreeSitterFeatureExtractor',
    'CustomFeatureExtractor',
    'LanguageConfig',
    'LanguageSupport',
    'FileClassifier',
    'BlockExtractor',
    'AIPatternProcessor',
    'get_unified_parser',
    'get_pattern_processor',
    'get_language_config',
    'get_language_support',
    'get_file_classifier',
    'get_block_extractor',
    'get_ai_pattern_processor'
] 