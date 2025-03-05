"""[2.0] File processor with pattern-based analysis.

This module provides file processing capabilities with:
1. Pattern-based file processing
2. AI-assisted file analysis
3. Pattern extraction
4. Cross-repository pattern learning
"""

from typing import Optional, Dict, List, Set, Tuple, Any
from tree_sitter_language_pack import SupportedLanguage
from indexer.file_utils import classify_file, get_relative_path, is_processable_file
from parsers.types import FileType, ParserType
from parsers.language_support import language_registry
from parsers.unified_parser import unified_parser
from parsers.pattern_processor import pattern_processor
from parsers.language_mapping import get_suggested_alternatives
from db.upsert_ops import UpsertCoordinator  # Use UpsertCoordinator for database operations
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
from parsers.types import ExtractedFeatures

# Initialize upsert coordinator
_upsert_coordinator = UpsertCoordinator()

class FileProcessor:
    """File processor with AI-assisted analysis."""
    
    def __init__(self):
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._pattern_cache = {}
        self._processing_stats = {
            "total_files": 0,
            "pattern_matches": 0,
            "ai_insights": 0,
            "failed_files": 0
        }
    
    async def initialize(self):
        """Initialize the processor."""
        if not self._initialized:
            try:
                # Initialize embedders
                await code_embedder.initialize()
                await doc_embedder.initialize()
                await arch_embedder.initialize()
                
                self._initialized = True
                log("File processor initialized with AI support", level="info")
            except Exception as e:
                log(f"Error initializing file processor: {e}", level="error")
                raise
    
    async def process_file(
        self,
        file_path: str,
        content: str,
        language: str,
        reference_patterns: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Process file with pattern recognition and AI analysis."""
        if not self._initialized:
            await self.initialize()
        
        self._processing_stats["total_files"] += 1
        
        try:
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
                features,
                patterns
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
            raise
    
    async def _extract_features(
        self,
        content: str,
        language: str
    ) -> ExtractedFeatures:
        """Extract code features with AI assistance."""
        # This is a placeholder - actual implementation would use language-specific parsers
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
        """Match content against reference patterns."""
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
        features: ExtractedFeatures,
        patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate AI insights for the file."""
        insights = []
        
        # Add pattern-based insights
        for pattern in patterns:
            insight = {
                "type": "pattern_match",
                "pattern_id": pattern["pattern_id"],
                "confidence": pattern["confidence"],
                "recommendations": await self._generate_recommendations(
                    content,
                    pattern
                )
            }
            insights.append(insight)
        
        # Add language-specific insights
        lang_insights = await self._generate_language_insights(
            content,
            language,
            features
        )
        insights.extend(lang_insights)
        
        return insights
    
    async def _generate_recommendations(
        self,
        content: str,
        pattern: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on pattern match."""
        # This is a placeholder - actual implementation would use AI models
        return [
            {
                "type": "improvement",
                "description": "Consider refactoring to better match the pattern",
                "priority": "medium"
            }
        ]
    
    async def _generate_language_insights(
        self,
        content: str,
        language: str,
        features: ExtractedFeatures
    ) -> List[Dict[str, Any]]:
        """Generate language-specific insights."""
        # This is a placeholder - actual implementation would use language-specific analysis
        return [
            {
                "type": "language_specific",
                "language": language,
                "description": "Language-specific insight",
                "confidence": 0.8
            }
        ]
    
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
    
    async def cleanup(self):
        """Clean up processor resources."""
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
async def cached_classify_file(file_path: str):
    """Cached file classification to avoid redundant classification."""
    return await classify_file(file_path)

@cached_in_request
async def cached_parse_file(rel_path: str, content: str, classification=None):
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
async def cached_get_patterns(classification):
    """Cached pattern retrieval to avoid redundant pattern loading."""
    return pattern_processor.get_patterns_for_file(classification)

@cached_in_request
async def cached_embed_code(content: str):
    """Cached code embedding to avoid redundant embedding generation."""
    return await code_embedder.embed_async(content)

@cached_in_request
async def cached_embed_doc(content: str):
    """Cached documentation embedding to avoid redundant embedding generation."""
    return await doc_embedder.embed_async(content) 