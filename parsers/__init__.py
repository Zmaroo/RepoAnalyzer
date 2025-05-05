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
    AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel,
    ParserResult, PatternValidationResult
)
from parsers.models import QueryResult, FileClassification, PATTERN_CATEGORIES
from parsers.parser_interfaces import BaseParserInterface, AIParserInterface
from parsers.base_parser import BaseParser
from parsers.unified_parser import UnifiedParser, get_unified_parser
from parsers.pattern_processor import PatternProcessor, get_pattern_processor
from parsers.feature_extractor import TreeSitterFeatureExtractor, FeatureExtractor
from parsers.language_config import LanguageConfig, get_language_config
from parsers.language_support import LanguageSupport, get_language_support
from parsers.file_classification import FileClassifier, get_file_classifier
from parsers.block_extractor import BlockExtractor, get_block_extractor
from parsers.ai_pattern_processor import AIPatternProcessor, get_ai_pattern_processor
from utils.logger import log
from utils.error_handling import AsyncErrorBoundary, handle_async_errors, ProcessingError, ErrorSeverity, ErrorAudit
from utils.shutdown import register_shutdown_handler
from utils.cache import UnifiedCache, cache_coordinator
from utils.health_monitor import ComponentStatus, global_health_monitor
from utils.async_runner import submit_async_task, cleanup_tasks
from utils.request_cache import request_cache_context
from utils.cache_analytics import get_cache_analytics
from db.transaction import transaction_scope

# Component initialization order aligned with app_init.py's PARSERS stage
PARSER_COMPONENTS = [
    ("language_config", get_language_config, "Configuration manager"),
    ("language_support", get_language_support, "Language support manager"),
    ("file_classifier", get_file_classifier, "File classifier"),
    ("block_extractor", get_block_extractor, "Block extractor"),
    ("pattern_processor", get_pattern_processor, "Pattern processor"),
    ("ai_pattern_processor", get_ai_pattern_processor, "AI pattern processor"),
    ("unified_parser", get_unified_parser, "Unified parser")
]

# Track component states
_component_states = {name: False for name, _, _ in PARSER_COMPONENTS}
_initialization_lock = asyncio.Lock()

async def initialize_parser_system() -> bool:
    """Initialize the parser system.
    
    This function is called by app_init.py during the PARSERS stage.
    It initializes all parser components in the correct dependency order.
    
    Returns:
        bool: True if initialization was successful
    """
    async with _initialization_lock:
        try:
            # Initialize components in order with health monitoring
            for name, get_component, description in PARSER_COMPONENTS:
                if _component_states[name]:
                    continue
                    
                try:
                    await global_health_monitor.update_component_status(
                        "parser_system",
                        ComponentStatus.INITIALIZING,
                        details={
                            "stage": f"initializing_{name}",
                            "description": description
                        }
                    )
                    
                    # Initialize component
                    component = await get_component()
                    if not component:
                        raise ProcessingError(f"Failed to initialize {name}")
                    
                    # Register shutdown handler through central system
                    register_shutdown_handler(component.cleanup)
                    
                    # Mark component as initialized
                    _component_states[name] = True
                    
                    await log(f"{name} initialized", level="info")
                    
                except Exception as e:
                    await log(f"Error initializing {name}: {e}", level="error")
                    await ErrorAudit.record_error(
                        e,
                        f"parser_initialization_{name}",
                        ProcessingError,
                        severity=ErrorSeverity.CRITICAL,
                        context={
                            "component": name,
                            "description": description
                        }
                    )
                    await global_health_monitor.update_component_status(
                        "parser_system",
                        ComponentStatus.UNHEALTHY,
                        error=True,
                        details={
                            "stage": f"initializing_{name}",
                            "error": str(e),
                            "description": description
                        }
                    )
                    return False
            
            return True
            
        except Exception as e:
            await log(f"Error initializing parser system: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                "parser_system_initialization",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL
            )
            return False

async def parse_source_code(source_code: str, language_id: str, file_type: FileType) -> Dict[str, Any]:
    """Parse source code using the unified parser.
    
    Args:
        source_code: The source code to parse
        language_id: The language identifier
        file_type: The type of file being parsed
        
    Returns:
        Dict[str, Any]: The parse result
    """
    try:
        # Ensure all required components are initialized
        required_components = ["unified_parser", "pattern_processor"]
        if not all(_component_states[comp] for comp in required_components):
            raise ProcessingError("Required parser components not initialized")
        
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
        await ErrorAudit.record_error(
            e,
            "source_code_parsing",
            ProcessingError,
            context={
                "language_id": language_id,
                "file_type": file_type.value
            }
        )
        return {}

# Export public interfaces
__all__ = [
    'initialize_parser_system',
    'parse_source_code',
    'UnifiedParser',
    'TreeSitterParser',
    'CustomParser',
    'PatternProcessor',
    'TreeSitterFeatureExtractor',
    'FeatureExtractor',
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