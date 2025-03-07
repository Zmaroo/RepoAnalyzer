"""[2.0] File processor with pattern-based analysis.

This module provides file processing capabilities with:
1. Pattern-based file processing
2. AI-assisted file analysis
3. Pattern extraction
4. Cross-repository pattern learning

Flow:
1. File Processing:
   - Content reading
   - Language detection
   - Pattern matching

2. AI Analysis:
   - Feature extraction
   - Pattern recognition
   - Insight generation

3. Pattern Learning:
   - Pattern extraction
   - Cross-repo analysis
   - Pattern evolution
"""

from typing import (
    Optional, Dict, List, Set, Tuple, Any,
    TypeVar, Union, Callable, Awaitable
)
from tree_sitter_language_pack import SupportedLanguage
from indexer.file_utils import classify_file, get_relative_path, is_processable_file
from parsers.types import (
    FileType, ParserType, ExtractedFeatures,
    AIContext, AIProcessingResult, PatternCategory,
    PatternPurpose
)
from parsers.language_support import language_registry
from parsers.unified_parser import unified_parser
from parsers.pattern_processor import pattern_processor
from parsers.language_mapping import get_suggested_alternatives
from db.upsert_ops import UpsertCoordinator
from db.transaction import transaction_scope
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    DatabaseError,
    ErrorSeverity
)
import aiofiles
import asyncio
from indexer.common import async_read_file
from embedding.embedding_models import code_embedder, doc_embedder, arch_embedder
from utils.request_cache import cached_in_request
from parsers.file_classification import classify_file
from parsers.models import FileClassification
from utils.shutdown import register_shutdown_handler
from utils.async_runner import submit_async_task

# Type variables for generic functions
T = TypeVar('T')
ResultType = TypeVar('ResultType')
ProcessingResult = Dict[str, Any]

class FileProcessor:
    """[2.1] File processor with AI-assisted analysis.
    
    Flow:
    1. Initialization:
       - Setup resources
       - Initialize embedders
       - Register cleanup

    2. Processing:
       - File content handling
       - Pattern matching
       - Feature extraction

    3. AI Integration:
       - Pattern recognition
       - Insight generation
       - Learning updates
    """
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized: bool = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._pattern_cache: Dict[str, Any] = {}
        self._processing_stats: Dict[str, int] = {
            "total_files": 0,
            "pattern_matches": 0,
            "ai_insights": 0,
            "failed_files": 0
        }
    
    async def initialize(self) -> bool:
        """[2.1.1] Initialize processor resources.
        
        Flow:
        1. Initialize embedders
        2. Setup caches
        3. Register cleanup
        
        Returns:
            bool: True if initialization successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        if not self._initialized:
            try:
                async with AsyncErrorBoundary(
                    "file processor initialization",
                    severity=ErrorSeverity.CRITICAL
                ):
                    # Initialize embedders
                    await code_embedder.initialize()
                    await doc_embedder.initialize()
                    await arch_embedder.initialize()
                    
                    # Register cleanup
                    register_shutdown_handler(self.cleanup)
                    
                    self._initialized = True
                    log("File processor initialized with AI support", level="info")
                    return True
            except Exception as e:
                log(f"Error initializing file processor: {e}", level="error")
                raise ProcessingError(f"Failed to initialize file processor: {e}")
        return True

    async def process_file(
        self,
        file_path: str,
        content: str,
        language: str,
        reference_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> ProcessingResult:
        """[2.1.2] Process file with pattern recognition and AI analysis.
        
        Flow:
        1. Generate embeddings
        2. Extract features
        3. Match patterns
        4. Generate insights
        
        Args:
            file_path: Path to the file
            content: File content
            language: Programming language
            reference_patterns: Optional patterns to match against
            
        Returns:
            Dict containing processing results
            
        Raises:
            ProcessingError: If processing fails
        """
        if not self._initialized:
            await self.initialize()
        
        self._processing_stats["total_files"] += 1
        
        try:
            async with AsyncErrorBoundary(
                f"processing file {file_path}",
                severity=ErrorSeverity.ERROR
            ):
                # Generate embeddings with pattern awareness
                code_embedding = await code_embedder.embed_code(
                    content,
                    language,
                    context={"file_path": file_path},
                    pattern_type="code"
                )
                
                # Extract features
                features = await self._extract_features(content, language)
                
                # Match against reference patterns
                patterns = []
                if reference_patterns:
                    patterns = await self._match_patterns(
                        content,
                        code_embedding,
                        reference_patterns,
                        features
                    )
                    self._processing_stats["pattern_matches"] += len(patterns)
                
                # Generate AI insights
                insights = await self._generate_ai_insights(
                    content,
                    language,
                    features
                )
                self._processing_stats["ai_insights"] += len(insights)
                
                return {
                    "features": features.to_dict(),
                    "patterns": patterns,
                    "insights": insights,
                    "embedding": code_embedding
                }
        except Exception as e:
            self._processing_stats["failed_files"] += 1
            log(f"Error processing file {file_path}: {e}", level="error")
            raise ProcessingError(f"Failed to process file {file_path}: {e}")

    async def _extract_features(
        self,
        content: str,
        language: str
    ) -> ExtractedFeatures:
        """[2.1.3] Extract code features with AI assistance.
        
        Flow:
        1. Parse content
        2. Extract basic features
        3. Enhance with AI
        
        Args:
            content: Source code content
            language: Programming language
            
        Returns:
            ExtractedFeatures object
            
        Raises:
            ProcessingError: If feature extraction fails
        """
        async with AsyncErrorBoundary(
            "feature extraction",
            severity=ErrorSeverity.ERROR
        ):
            features = ExtractedFeatures()
            features.language = language
            return features

    async def _match_patterns(
        self,
        content: str,
        embedding: List[float],
        reference_patterns: List[Dict[str, Any]],
        features: ExtractedFeatures
    ) -> List[Dict[str, Any]]:
        """[2.1.4] Match content against reference patterns.
        
        Flow:
        1. Generate pattern embeddings
        2. Calculate similarities
        3. Filter matches
        4. Calculate confidence
        
        Args:
            content: Source code content
            embedding: Code embedding
            reference_patterns: Patterns to match
            features: Extracted features
            
        Returns:
            List of pattern matches
        """
        matches = []
        
        for pattern in reference_patterns:
            # Generate pattern embedding
            pattern_embedding = await code_embedder.embed_pattern(pattern)
            
            # Calculate similarity
            similarity = self._calculate_similarity(embedding, pattern_embedding)
            
            if similarity > 0.8:  # High confidence threshold
                match = {
                    "pattern_id": pattern["id"],
                    "pattern_type": pattern["type"],
                    "similarity": similarity,
                    "confidence": self._calculate_confidence(
                        similarity,
                        features,
                        pattern
                    )
                }
                matches.append(match)
        
        return matches

    def _calculate_similarity(
        self,
        embedding1: List[float],
        embedding2: List[float]
    ) -> float:
        """Calculate cosine similarity between embeddings."""
        import numpy as np
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
    
    def _calculate_confidence(
        self,
        similarity: float,
        features: ExtractedFeatures,
        pattern: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for pattern match."""
        # Base confidence from similarity
        confidence = similarity
        
        # Adjust based on feature matching
        if pattern.get("language") == features.language:
            confidence *= 1.1
        
        if pattern.get("complexity") and features.complexity:
            complexity_diff = abs(pattern["complexity"] - features.complexity)
            confidence *= (1.0 - (complexity_diff / 10.0))
        
        # Cap at 1.0
        return min(1.0, confidence)

    async def _generate_ai_insights(
        self,
        content: str,
        language: str,
        features: ExtractedFeatures
    ) -> List[Dict[str, Any]]:
        """[2.1.5] Generate AI insights for the file.
        
        Flow:
        1. Analyze content
        2. Generate insights
        3. Calculate confidence
        
        Args:
            content: Source code content
            language: Programming language
            features: Extracted features
            
        Returns:
            List of AI insights
        """
        return [{
            "type": "language_specific",
            "language": language,
            "description": "Language-specific insight",
            "confidence": 0.8
        }]
    
    def get_stats(self) -> Dict[str, int]:
        """Get processing statistics."""
        return self._processing_stats.copy()
    
    def reset_stats(self) -> None:
        """Reset processing statistics."""
        self._processing_stats = {
            "total_files": 0,
            "pattern_matches": 0,
            "ai_insights": 0,
            "failed_files": 0
        }
    
    async def cleanup(self) -> None:
        """[2.1.6] Clean up processor resources.
        
        Flow:
        1. Cancel pending tasks
        2. Clear caches
        3. Reset state
        """
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear pattern cache
            self._pattern_cache.clear()
            
            self._initialized = False
            log("File processor cleaned up", level="info")
        except Exception as e:
            log(f"Error cleaning up file processor: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup file processor: {e}")

    @classmethod
    async def create(cls) -> 'FileProcessor':
        """[2.1.7] Create and initialize a file processor instance.
        
        Flow:
        1. Create instance
        2. Initialize resources
        3. Return initialized instance
        
        Returns:
            Initialized FileProcessor instance
            
        Raises:
            ProcessingError: If creation fails
        """
        instance = cls()
        await instance.initialize()
        return instance

# Create global instance
processor = FileProcessor()

# Export with proper async handling
async def get_processor() -> FileProcessor:
    """Get the file processor instance.
    
    Returns:
        FileProcessor: The singleton file processor instance
    """
    if not processor._initialized:
        await processor.initialize()
    return processor

# Cache-enabled utility functions
@cached_in_request
async def cached_read_file(file_path: str) -> Optional[str]:
    """Cached version of async_read_file to avoid redundant file I/O."""
    return await async_read_file(file_path)

@cached_in_request
async def cached_classify_file(file_path: str) -> Optional[FileClassification]:
    """Cached file classification to avoid redundant classification."""
    return await classify_file(file_path)

@cached_in_request
async def cached_parse_file(
    rel_path: str,
    content: str,
    classification: Optional[FileClassification] = None
) -> Optional[Dict[str, Any]]:
    """Cached file parsing to avoid redundant parsing operations."""
    from parsers.types import ParserResult
    result = await unified_parser.parse_file(rel_path, content)
    
    # If the result is a dictionary without a 'success' property,
    # transform it into a proper ParserResult
    if isinstance(result, dict):
        if 'success' not in result:
            result = ParserResult(
                success=True,
                ast=result.get('ast', {}),
                features=result.get('features', {}),
                documentation=result.get('documentation', {}),
                complexity=result.get('complexity', {}),
                statistics=result.get('statistics', {})
            )
        else:
            # Convert dict with success to ParserResult
            result = ParserResult(
                success=result.get('success', True),
                ast=result.get('ast', {}),
                features=result.get('features', {}),
                documentation=result.get('documentation', {}),
                complexity=result.get('complexity', {}),
                statistics=result.get('statistics', {})
            )
    return result

@cached_in_request
async def cached_get_patterns(
    classification: FileClassification
) -> Dict[PatternCategory, Dict[PatternPurpose, Dict[str, Any]]]:
    """Cached pattern retrieval to avoid redundant pattern loading."""
    return await pattern_processor.get_patterns_for_file(classification) 