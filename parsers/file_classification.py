"""
File classification and language detection module.

This module provides tools for classifying files based on their content and extension,
determining the appropriate parser type, and extracting language information.
"""

import os
import re
from typing import Dict, Optional, Tuple, List, Set, Union, Callable, Any
import asyncio
from dataclasses import dataclass, field

from parsers.models import FileClassification, FileMetadata
from parsers.types import ParserType, FileType, AICapability, AIContext, AIProcessingResult, InteractionType, ConfidenceLevel
from parsers.language_mapping import (
    # Import mappings
    TREE_SITTER_LANGUAGES,
    CUSTOM_PARSER_LANGUAGES,
    FULL_EXTENSION_MAP,
    FILENAME_MAP,
    BINARY_EXTENSIONS,
    
    # Import functions
    normalize_language_name,
    is_supported_language,
    get_parser_type,
    get_file_type,
    detect_language_from_filename,
    detect_language_from_content,
    detect_language,
    get_complete_language_info,
    get_parser_info_for_language,
    is_binary_extension,
    get_ai_capabilities
)
from parsers.parser_interfaces import AIParserInterface
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary, ErrorSeverity, ProcessingError
from utils.shutdown import register_shutdown_handler

# Track initialization state and tasks
_initialized = False
_pending_tasks: Set[asyncio.Task] = set()

@dataclass
class FileClassifier(AIParserInterface):
    """[3.1] File classification system with AI capabilities."""
    
    def __init__(self):
        """Initialize file classifier."""
        super().__init__(
            language_id="file_classifier",
            file_type=FileType.CODE,
            capabilities={
                AICapability.CODE_UNDERSTANDING,
                AICapability.DOCUMENTATION
            }
        )
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._cache = {}
        self._lock = asyncio.Lock()
    
    async def ensure_initialized(self):
        """Ensure the classifier is initialized."""
        if not self._initialized:
            raise ProcessingError("File classifier not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'FileClassifier':
        """[3.1.1] Create and initialize a file classifier instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("file classifier initialization"):
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                log("File classifier initialized", level="info")
                return instance
        except Exception as e:
            log(f"Error initializing file classifier: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize file classifier: {e}")
    
    async def classify_file(
        self,
        file_path: str,
        content: Optional[str] = None
    ) -> FileClassification:
        """[3.1.2] Classify a file based on its path and optional content."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary(f"classify_file_{file_path}"):
            try:
                # Check cache first
                cache_key = f"{file_path}:{hash(content) if content else ''}"
                if cache_key in self._cache:
                    return self._cache[cache_key]
                
                # Detect language from filename
                language_id = detect_language_from_filename(file_path)
                if not language_id:
                    language_id = await self._detect_language_from_content(content) if content else "unknown"
                
                # Get complete language information
                language_info = get_complete_language_info(language_id)
                
                # Create classification
                classification = FileClassification(
                    file_path=file_path,
                    language_id=language_info["canonical_name"],
                    parser_type=language_info["parser_type"],
                    file_type=language_info["file_type"],
                    is_binary=await self._is_binary_content(content) if content else False
                )
                
                # Cache result
                self._cache[cache_key] = classification
                
                return classification
            except Exception as e:
                log(f"Error classifying file {file_path}: {e}", level="error")
                raise ProcessingError(f"Failed to classify file {file_path}: {e}")
    
    async def process_with_ai(
        self,
        source_code: str,
        context: AIContext
    ) -> AIProcessingResult:
        """[3.1.3] Process file with AI assistance."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("file classifier AI processing"):
            try:
                results = AIProcessingResult(success=True)
                
                # Process with understanding capability
                if AICapability.CODE_UNDERSTANDING in self.capabilities:
                    understanding = await self._analyze_file_characteristics(source_code, context)
                    results.context_info.update(understanding)
                
                # Process with documentation capability
                if AICapability.DOCUMENTATION in self.capabilities:
                    documentation = await self._analyze_file_documentation(source_code, context)
                    results.ai_insights.update(documentation)
                
                return results
            except Exception as e:
                log(f"Error in file classifier AI processing: {e}", level="error")
                return AIProcessingResult(
                    success=False,
                    response=f"Error processing with AI: {str(e)}"
                )
    
    async def _analyze_file_characteristics(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """[3.1.4] Analyze file characteristics with AI."""
        characteristics = {
            "structure": await self._analyze_file_structure(source_code),
            "patterns": await self._identify_file_patterns(source_code),
            "complexity": await self._assess_file_complexity(source_code)
        }
        
        # Add language-specific analysis
        if context.project.language_id != "unknown":
            characteristics.update(await self._analyze_language_specific(
                source_code,
                context.project.language_id
            ))
        
        return characteristics
    
    async def _analyze_file_documentation(
        self,
        source_code: str,
        context: AIContext
    ) -> Dict[str, Any]:
        """[3.1.5] Analyze file documentation with AI."""
        return {
            "doc_coverage": await self._analyze_documentation_coverage(source_code),
            "doc_quality": await self._assess_documentation_quality(source_code),
            "doc_patterns": await self._identify_documentation_patterns(source_code)
        }
    
    async def _analyze_file_structure(self, source_code: str) -> Dict[str, Any]:
        """[3.1.6] Analyze file structure."""
        return {
            "line_count": len(source_code.splitlines()),
            "block_structure": await self._analyze_block_structure(source_code),
            "indentation": await self._analyze_indentation(source_code)
        }
    
    async def _identify_file_patterns(self, source_code: str) -> List[Dict[str, Any]]:
        """[3.1.7] Identify common file patterns."""
        patterns = []
        
        # Check for common file patterns
        if await self._is_config_file(source_code):
            patterns.append({
                "type": "config",
                "confidence": 0.9,
                "indicators": ["key-value pairs", "structured data"]
            })
        
        if await self._is_test_file(source_code):
            patterns.append({
                "type": "test",
                "confidence": 0.8,
                "indicators": ["test functions", "assertions"]
            })
        
        if await self._is_documentation_file(source_code):
            patterns.append({
                "type": "documentation",
                "confidence": 0.85,
                "indicators": ["extensive comments", "docstrings"]
            })
        
        return patterns
    
    async def _assess_file_complexity(self, source_code: str) -> Dict[str, float]:
        """[3.1.8] Assess file complexity."""
        return {
            "cognitive_complexity": await self._calculate_cognitive_complexity(source_code),
            "structural_complexity": await self._calculate_structural_complexity(source_code),
            "documentation_ratio": await self._calculate_documentation_ratio(source_code)
        }
    
    async def _analyze_language_specific(
        self,
        source_code: str,
        language_id: str
    ) -> Dict[str, Any]:
        """[3.1.9] Analyze language-specific characteristics."""
        return {
            "language_features": await self._identify_language_features(source_code, language_id),
            "style_compliance": await self._check_style_compliance(source_code, language_id),
            "best_practices": await self._check_best_practices(source_code, language_id)
        }
    
    async def _detect_language_from_content(self, content: Optional[str]) -> str:
        """[3.1.10] Detect language from file content."""
        if not content:
            return "unknown"
            
        # Check for common language indicators
        indicators = {
            "python": [r"^import\s+\w+", r"^from\s+\w+\s+import", r"def\s+\w+\s*\("],
            "javascript": [r"^const\s+\w+", r"^let\s+\w+", r"function\s+\w+\s*\("],
            "typescript": [r"^interface\s+\w+", r"^type\s+\w+", r":\s*\w+[]?"],
            "markdown": [r"^#\s+", r"^\*\s+", r"^-\s+"],
            "html": [r"<!DOCTYPE\s+html>", r"<html>", r"<head>"],
            "json": [r"^\s*{", r"^\s*\[", r"\"\w+\":\s*"],
            "yaml": [r"^---", r"^\w+:", r"^\s*-\s+\w+:"]
        }
        
        matches = {}
        for lang, patterns in indicators.items():
            matches[lang] = sum(1 for pattern in patterns if re.search(pattern, content, re.MULTILINE))
        
        if matches:
            best_match = max(matches.items(), key=lambda x: x[1])
            if best_match[1] > 0:
                return best_match[0]
        
        return "unknown"
    
    async def _is_binary_content(self, content: Optional[str]) -> bool:
        """[3.1.11] Check if content appears to be binary."""
        if not content:
            return False
            
        # Check for null bytes and high concentration of non-printable characters
        try:
            return b"\x00" in content.encode("utf-8") or \
                   sum(1 for c in content if not (32 <= ord(c) <= 126)) > len(content) * 0.3
        except UnicodeEncodeError:
            return True
    
    async def cleanup(self):
        """[3.1.12] Clean up classifier resources."""
        try:
            if not self._initialized:
                return
                
            # Clear cache
            self._cache.clear()
            
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            self._initialized = False
            log("File classifier cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up file classifier: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file classifier: {e}")

    async def analyze_with_patterns(
        self,
        file_path: str,
        content: str,
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze file using learned patterns."""
        classification = await self.classify_file(file_path, content)
        pattern_matches = await self._match_patterns(content, patterns)
        return {
            "classification": classification,
            "pattern_matches": pattern_matches
        }

# Global instance
_file_classifier = None

async def get_file_classifier() -> FileClassifier:
    """[3.2] Get the global file classifier instance."""
    global _file_classifier
    if not _file_classifier:
        _file_classifier = await FileClassifier.create()
    return _file_classifier

@handle_async_errors(error_types=(Exception,))
async def initialize():
    """Initialize file classification resources."""
    global _initialized
    if not _initialized:
        try:
            async with AsyncErrorBoundary("file_classification_initialization"):
                # No special initialization needed yet
                _initialized = True
                log("File classification initialized", level="info")
        except Exception as e:
            log(f"Error initializing file classification: {e}", level="error")
            raise

@handle_async_errors(error_types=(Exception,))
async def classify_file(file_path: str, content: Optional[str] = None) -> FileClassification:
    """
    Classify a file based on its path and optionally its content.
    
    Args:
        file_path: Path to the file
        content: Optional file content for more accurate classification
        
    Returns:
        FileClassification object with parser type and language information
    """
    if not _initialized:
        await initialize()
        
    async with AsyncErrorBoundary("classify_file"):
        # Use the enhanced language detection with confidence score
        task = asyncio.create_task(detect_language(file_path, content))
        _pending_tasks.add(task)
        try:
            language_id, confidence = await task
        finally:
            _pending_tasks.remove(task)
        
        # Log detection confidence if it's low
        if confidence < 0.5:
            log(f"Low confidence ({confidence:.2f}) language detection for {file_path}: {language_id}", level="debug")
        
        # Get parser info for the detected language
        task = asyncio.create_task(get_parser_info_for_language(language_id))
        _pending_tasks.add(task)
        try:
            parser_info = await task
        finally:
            _pending_tasks.remove(task)
        
        # Check if file is binary
        task = asyncio.create_task(_is_likely_binary(file_path, content))
        _pending_tasks.add(task)
        try:
            is_binary = await task
        finally:
            _pending_tasks.remove(task)
        
        # Create classification
        classification = FileClassification(
            file_path=file_path,
            language_id=parser_info["language_id"],
            parser_type=parser_info["parser_type"],
            file_type=parser_info["file_type"],
            is_binary=is_binary,
        )
        
        return classification

@handle_async_errors(error_types=(Exception,))
async def _is_likely_binary(file_path: str, content: Optional[str] = None) -> bool:
    """
    Determine if a file is likely binary.
    
    Args:
        file_path: Path to the file
        content: Optional file content
        
    Returns:
        True if likely binary, False otherwise
    """
    # Check extension first using language_mapping function
    _, ext = os.path.splitext(file_path)
    if is_binary_extension(ext):
        return True
    
    # If content provided, check for null bytes
    if content:
        # Check sample of content for null bytes
        sample = content[:4096] if len(content) > 4096 else content
        if '\0' in sample:
            return True
    
    return False

@handle_async_errors(error_types=(Exception,))
async def get_supported_languages() -> Dict[str, ParserType]:
    """
    Get a dictionary of all supported languages and their parser types.
    Returns:
        Dictionary with language IDs as keys and parser types as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_languages as get_langs
    task = asyncio.create_task(get_langs())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

@handle_async_errors(error_types=(Exception,))
async def get_supported_extensions() -> Dict[str, str]:
    """
    Get a dictionary of all supported file extensions and their corresponding languages.
    Returns:
        Dictionary with extensions as keys and language IDs as values
    """
    # Use the function from language_mapping.py
    from parsers.language_mapping import get_supported_extensions as get_exts
    task = asyncio.create_task(get_exts())
    _pending_tasks.add(task)
    try:
        return await task
    finally:
        _pending_tasks.remove(task)

async def cleanup():
    """Clean up file classification resources."""
    global _initialized
    try:
        # Clean up any pending tasks
        if _pending_tasks:
            for task in _pending_tasks:
                task.cancel()
            await asyncio.gather(*_pending_tasks, return_exceptions=True)
            _pending_tasks.clear()
        
        _initialized = False
        log("File classification cleaned up", level="info")
    except Exception as e:
        log(f"Error cleaning up file classification: {e}", level="error")

# Register cleanup handler
register_shutdown_handler(cleanup) 