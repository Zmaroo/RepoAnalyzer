"""[0.0] Parser package initialization.

This module provides centralized initialization and cleanup for all parser components:
1. Language Support & Registry
2. File Classification & Analysis
3. Tree-sitter & Custom Parsers
4. Feature & Block Extraction
5. Pattern Processing & AI Integration
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
from dataclasses import dataclass, field
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ProcessingError
from utils.shutdown import register_shutdown_handler

# Core types and interfaces
from .types import (
    FileType,
    ParserType,
    AICapability,
    AIContext,
    AIProcessingResult,
    InteractionType,
    ConfidenceLevel,
    Documentation,
    ComplexityMetrics,
    ExtractedFeatures,
    PatternCategory,
    PatternPurpose,
    PatternType,
    PatternDefinition,
    QueryPattern,
    PatternInfo
)

# Core models
from .models import (
    FileClassification,
    ParserResult,
    BaseNodeDict,
    TreeSitterNodeDict,
    FileMetadata,
    LanguageFeatures,
    PatternMatch,
    QueryResult,
    ProcessedPattern,
    AIPatternResult
)

# Parser interfaces
from .parser_interfaces import (
    BaseParserInterface,
    ParserRegistryInterface,
    AIParserInterface
)

# Language support
from .language_support import (
    language_registry,
    get_parser_availability,
    determine_file_type,
    is_documentation_code,
    get_language_by_extension,
    get_extensions_for_language
)

# Language mapping
from .language_mapping import (
    normalize_language_name,
    get_parser_type,
    get_file_type,
    get_ai_capabilities,
    get_fallback_parser_type,
    get_language_features,
    get_suggested_alternatives,
    detect_language_from_filename,
    get_complete_language_info,
    get_parser_info_for_language
)

# File classification
from .file_classification import (
    get_file_classifier,
    classify_file,
    get_supported_languages,
    get_supported_extensions
)

# Tree-sitter parser
from .tree_sitter_parser import (
    TreeSitterParser,
    get_tree_sitter_parser
)

# Feature extraction
from .feature_extractor import (
    BaseFeatureExtractor,
    TreeSitterFeatureExtractor,
    CustomFeatureExtractor,
    UnifiedFeatureExtractor
)

# Block extraction
from .block_extractor import (
    TreeSitterBlockExtractor,
    get_block_extractor,
    ExtractedBlock
)

# Pattern processing
from .pattern_processor import (
    PatternProcessor,
    pattern_processor,
    process_pattern,
    validate_pattern
)

# AI pattern processing
from .ai_pattern_processor import (
    AIPatternProcessor,
    process_with_ai,
    validate_with_ai
)

# Unified parser
from .unified_parser import (
    UnifiedParser,
    get_unified_parser
)

# Custom parsers
from .custom_parsers import CUSTOM_PARSER_CLASSES

# Version information
__version__ = "3.2.0"
__author__ = "RepoAnalyzer Team"

# Track initialization state
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """[0.1] Initialize parser package components."""
    global _initialized
    
    if _initialized:
        return
    
    try:
        async with AsyncErrorBoundary("parser initialization"):
            # Initialize language registry first
            task = asyncio.create_task(language_registry.initialize())
            _pending_tasks.add(task)
            try:
                await task
            finally:
                _pending_tasks.remove(task)
            
            # Initialize file classifier
            classifier = await get_file_classifier()
            task = asyncio.create_task(classifier.initialize())
            _pending_tasks.add(task)
            try:
                await task
            finally:
                _pending_tasks.remove(task)
            
            # Initialize pattern processor
            task = asyncio.create_task(pattern_processor.initialize())
            _pending_tasks.add(task)
            try:
                await task
            finally:
                _pending_tasks.remove(task)
            
            _initialized = True
            log("Parser components initialized successfully", level="info")
    except Exception as e:
        log(f"Error initializing parser components: {e}", level="error")
        raise ProcessingError(f"Failed to initialize parser components: {e}")

async def cleanup():
    """[0.2] Clean up parser package resources."""
    global _initialized
    
    try:
        # Clean up in reverse initialization order
        cleanup_tasks = []
        
        # Clean up pattern processor
        task = asyncio.create_task(pattern_processor.cleanup())
        cleanup_tasks.append(task)
        
        # Clean up file classifier
        classifier = await get_file_classifier()
        task = asyncio.create_task(classifier.cleanup())
        cleanup_tasks.append(task)
        
        # Clean up language registry
        task = asyncio.create_task(language_registry.cleanup())
        cleanup_tasks.append(task)
        
        # Wait for all cleanup tasks
        await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Clean up any remaining pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("Parser components cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up parser components: {e}", level="error")
        raise ProcessingError(f"Failed to cleanup parser components: {e}")

# Register cleanup handler
register_shutdown_handler(cleanup)

# Export public interfaces
__all__ = [
    # Core types
    'FileType',
    'ParserType',
    'AICapability',
    'AIContext',
    'AIProcessingResult',
    'InteractionType',
    'ConfidenceLevel',
    'Documentation',
    'ComplexityMetrics',
    'ExtractedFeatures',
    'PatternCategory',
    'PatternPurpose',
    'PatternType',
    'PatternDefinition',
    'QueryPattern',
    'PatternInfo',
    
    # Core models
    'FileClassification',
    'ParserResult',
    'BaseNodeDict',
    'TreeSitterNodeDict',
    'FileMetadata',
    'LanguageFeatures',
    'PatternMatch',
    'QueryResult',
    'ProcessedPattern',
    'AIPatternResult',
    
    # Interfaces
    'BaseParserInterface',
    'ParserRegistryInterface',
    'AIParserInterface',
    
    # Language support
    'language_registry',
    'get_parser_availability',
    'determine_file_type',
    'is_documentation_code',
    'get_language_by_extension',
    'get_extensions_for_language',
    
    # Language mapping
    'normalize_language_name',
    'get_parser_type',
    'get_file_type',
    'get_ai_capabilities',
    'get_fallback_parser_type',
    'get_language_features',
    'get_suggested_alternatives',
    'detect_language_from_filename',
    'get_complete_language_info',
    'get_parser_info_for_language',
    
    # File classification
    'get_file_classifier',
    'classify_file',
    'get_supported_languages',
    'get_supported_extensions',
    
    # Tree-sitter parser
    'TreeSitterParser',
    'get_tree_sitter_parser',
    
    # Feature extraction
    'BaseFeatureExtractor',
    'TreeSitterFeatureExtractor',
    'CustomFeatureExtractor',
    'UnifiedFeatureExtractor',
    
    # Block extraction
    'TreeSitterBlockExtractor',
    'get_block_extractor',
    'ExtractedBlock',
    
    # Pattern processing
    'PatternProcessor',
    'pattern_processor',
    'process_pattern',
    'validate_pattern',
    
    # AI pattern processing
    'AIPatternProcessor',
    'process_with_ai',
    'validate_with_ai',
    
    # Unified parser
    'UnifiedParser',
    'get_unified_parser',
    
    # Custom parsers
    'CUSTOM_PARSER_CLASSES',
    
    # Package functions
    'initialize',
    'cleanup'
] 