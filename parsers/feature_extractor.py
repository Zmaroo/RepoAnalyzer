"""Feature extraction management.

This module provides feature extraction capabilities for languages,
integrating with the parser system and caching infrastructure.
"""

from typing import Dict, Optional, Set, List, Any, Union
import asyncio
import time
import psutil
from dataclasses import dataclass, field
from parsers.types import (
    FileType, ParserType, AICapability, AIContext,
    ExtractedFeatures, FeatureCategory, Documentation,
    ComplexityMetrics, PatternCategory, PatternPurpose
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
class CacheStats:
    """Cache statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    memory_usage: int = 0
    avg_access_time: float = 0.0
    access_times: List[float] = field(default_factory=list)

@dataclass
class FeatureExtractor(BaseParser):
    """Feature extraction management.
    
    This class manages feature extraction for languages,
    integrating with the parser system for efficient feature extraction.
    
    Attributes:
        language_id (str): The identifier for the language
        features (ExtractedFeatures): The extracted features
        documentation (Documentation): The extracted documentation
        metrics (ComplexityMetrics): The complexity metrics
    """
    
    def __init__(self, language_id: str):
        """Initialize feature extractor.
        
        Args:
            language_id: The identifier for the language
        """
        super().__init__(
            language_id=language_id,
            file_type=FileType.CODE,
            parser_type=ParserType.CUSTOM
        )
        self.features = ExtractedFeatures()
        self.documentation = Documentation()
        self.metrics = ComplexityMetrics()
        
        # Cache configuration
        self._cache_stats = CacheStats()
        self._cache_config = {
            "max_size": 1000,  # Maximum number of cached items
            "max_memory": 100 * 1024 * 1024,  # 100MB max memory usage
            "ttl": 3600,  # 1 hour TTL
            "cleanup_interval": 300  # 5 minutes cleanup interval
        }
        self._last_cleanup = time.time()
        
        # Pattern tracking
        self._pattern_usage_stats = {}
        self._pattern_success_rates = {}
        self._adaptive_thresholds = {}
        self._learning_enabled = True
        
        # Register with shutdown handler
        register_shutdown_handler(self._cleanup)
    
    async def initialize(self) -> bool:
        """Initialize feature extractor.
        
        Returns:
            bool: True if initialization was successful
            
        Raises:
            ProcessingError: If initialization fails
        """
        try:
            # Initialize base class first
            if not await super().initialize():
                return False
            
            async with AsyncErrorBoundary(f"feature_extractor_initialization_{self.language_id}"):
                # Load features through async_runner
                init_task = submit_async_task(self._load_features())
                await asyncio.wrap_future(init_task)
                
                if not all([self.features, self.documentation, self.metrics]):
                    raise ProcessingError(f"Failed to load features for {self.language_id}")
                
                await log(f"Feature extractor initialized for {self.language_id}", level="info")
                return True
                
        except Exception as e:
            await log(f"Error initializing feature extractor: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"feature_extractor_initialization_{self.language_id}",
                ProcessingError,
                severity=ErrorSeverity.CRITICAL,
                context={"language": self.language_id}
            )
            await global_health_monitor.update_component_status(
                f"feature_extractor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"extractor_error": str(e)}
            )
            raise ProcessingError(f"Failed to initialize feature extractor for {self.language_id}: {e}")
    
    async def _load_features(self) -> None:
        """Load feature extraction configuration from storage."""
        try:
            # Update health status
            await global_health_monitor.update_component_status(
                f"feature_extractor_{self.language_id}",
                ComponentStatus.INITIALIZING,
                details={"stage": "loading_features"}
            )
            
            async with transaction_scope(distributed=True) as txn:
                # Record transaction start
                await txn.record_operation("load_features_start", {
                    "language_id": self.language_id,
                    "start_time": time.time()
                })
                
                # Load features
                features_result = await txn.fetchrow("""
                    SELECT * FROM language_features
                    WHERE language_id = $1
                """, self.language_id)
                
                if features_result:
                    self.features = ExtractedFeatures(**features_result)
                    
                # Load documentation
                doc_result = await txn.fetchrow("""
                    SELECT * FROM language_documentation
                    WHERE language_id = $1
                """, self.language_id)
                
                if doc_result:
                    self.documentation = Documentation(**doc_result)
                    
                # Load metrics
                metrics_result = await txn.fetchrow("""
                    SELECT * FROM language_metrics
                    WHERE language_id = $1
                """, self.language_id)
                
                if metrics_result:
                    self.metrics = ComplexityMetrics(**metrics_result)
                
                # Record transaction metrics
                await txn.record_operation("load_features_complete", {
                    "language_id": self.language_id,
                    "features_loaded": bool(features_result),
                    "docs_loaded": bool(doc_result),
                    "metrics_loaded": bool(metrics_result),
                    "end_time": time.time()
                })
                
                # Update final health status
                await global_health_monitor.update_component_status(
                    f"feature_extractor_{self.language_id}",
                    ComponentStatus.HEALTHY,
                    details={
                        "features_loaded": bool(features_result),
                        "docs_loaded": bool(doc_result),
                        "metrics_loaded": bool(metrics_result)
                    }
                )
                    
        except Exception as e:
            await log(f"Error loading features: {e}", level="error")
            await global_health_monitor.update_component_status(
                f"feature_extractor_{self.language_id}",
                ComponentStatus.UNHEALTHY,
                error=True,
                details={"error": str(e)}
            )
            raise ProcessingError(f"Failed to load features: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def extract_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from AST.
        
        Args:
            ast: The AST to extract features from
            source_code: The original source code
            
        Returns:
            ExtractedFeatures: The extracted features
        """
        try:
            async with AsyncErrorBoundary(f"feature_extraction_{self.language_id}"):
                # Check file size limits
                MAX_FILE_SIZE = 1024 * 1024  # 1MB
                if len(source_code) > MAX_FILE_SIZE:
                    await log(f"File size exceeds limit: {len(source_code)} bytes", level="warning")
                    # Process in chunks
                    return await self._extract_features_chunked(ast, source_code)
                
                # Extract through async_runner
                extract_task = submit_async_task(self._extract_all_features(ast, source_code))
                features = await asyncio.wrap_future(extract_task)
                
                # Update local state
                self.features = features
                
                await log(f"Features extracted for {self.language_id}", level="info")
                return features
                
        except Exception as e:
            await log(f"Error extracting features: {e}", level="error")
            await ErrorAudit.record_error(
                e,
                f"feature_extraction_{self.language_id}",
                ProcessingError,
                context={"ast_size": len(str(ast))}
            )
            return ExtractedFeatures()
    
    async def _extract_all_features(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract all features from AST."""
        features = ExtractedFeatures()
        
        # Monitor memory usage
        memory_usage = psutil.Process().memory_info().rss
        MAX_MEMORY = 1024 * 1024 * 1024  # 1GB
        
        async with request_cache_context() as cache:
            for category in FeatureCategory:
                # Check memory usage
                current_memory = psutil.Process().memory_info().rss
                if current_memory - memory_usage > MAX_MEMORY:
                    await log("Memory limit exceeded, stopping feature extraction", level="warning")
                    break
                
                # Extract features for category
                category_features = await self._extract_category_features(category, ast, source_code)
                features.update({category: category_features})
        
        # Extract documentation
        documentation = await self._extract_documentation(source_code)
        features.documentation = documentation
        
        # Extract metrics
        metrics = await self._extract_metrics(ast)
        features.metrics = metrics
        
        return features
    
    async def _extract_syntax_features(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Extract syntax features from AST."""
        features = {}
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            # Get patterns for syntax category
            patterns = await pattern_processor.get_patterns_for_category(
                FeatureCategory.SYNTAX,
                PatternPurpose.UNDERSTANDING,
                self.language_id,
                self.parser_type
            )
            
            if patterns:
                for pattern in patterns:
                    # Check if pattern should be used
                    if not await self._should_use_pattern(pattern["name"]):
                        continue
                    
                    start_time = time.time()
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            ast,
                            self.language_id
                        )
                        
                        extraction_time = time.time() - start_time
                        
                        if processed.matches:
                            features[pattern["name"]] = processed.matches
                            # Update pattern stats with success
                            await self._update_pattern_stats(
                                pattern["name"],
                                True,
                                extraction_time,
                                len(processed.matches)
                            )
                            
                    except Exception as e:
                        extraction_time = time.time() - start_time
                        # Update pattern stats with failure
                        await self._update_pattern_stats(
                            pattern["name"],
                            False,
                            extraction_time,
                            0
                        )
                        await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                        continue
                        
        except Exception as e:
            await log(f"Error extracting syntax features: {e}", level="error")
            
        return features
    
    async def _extract_semantic_features(self, ast: Dict[str, Any]) -> Dict[str, Any]:
        """Extract semantic features from AST."""
        features = {}
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            # Get patterns for semantics category
            patterns = await pattern_processor.get_patterns_for_category(
                FeatureCategory.SEMANTICS,
                PatternPurpose.UNDERSTANDING,
                self.language_id,
                self.parser_type
            )
            
            if patterns:
                for pattern in patterns:
                    # Check if pattern should be used
                    if not await self._should_use_pattern(pattern["name"]):
                        continue
                    
                    start_time = time.time()
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            ast,
                            self.language_id
                        )
                        
                        extraction_time = time.time() - start_time
                        
                        if processed.matches:
                            features[pattern["name"]] = processed.matches
                            # Update pattern stats with success
                            await self._update_pattern_stats(
                                pattern["name"],
                                True,
                                extraction_time,
                                len(processed.matches)
                            )
                            
                    except Exception as e:
                        extraction_time = time.time() - start_time
                        # Update pattern stats with failure
                        await self._update_pattern_stats(
                            pattern["name"],
                            False,
                            extraction_time,
                            0
                        )
                        await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                        continue
                        
        except Exception as e:
            await log(f"Error extracting semantic features: {e}", level="error")
            
        return features
    
    async def _extract_documentation(self, source_code: str) -> Documentation:
        """Extract documentation from source code."""
        documentation = Documentation()
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            # Get patterns for documentation category
            patterns = await pattern_processor.get_patterns_for_category(
                FeatureCategory.DOCUMENTATION,
                PatternPurpose.UNDERSTANDING,
                self.language_id,
                self.parser_type
            )
            
            if patterns:
                for pattern in patterns:
                    # Check if pattern should be used
                    if not await self._should_use_pattern(pattern["name"]):
                        continue
                    
                    start_time = time.time()
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            source_code,
                            self.language_id
                        )
                        
                        extraction_time = time.time() - start_time
                        
                        if processed.matches:
                            # Extract docstrings
                            if pattern["name"] == "docstring":
                                documentation.docstrings.extend(processed.matches)
                                for doc in processed.matches:
                                    if "text" in doc:
                                        documentation.content += doc["text"] + "\n"
                            
                            # Extract comments
                            elif pattern["name"] == "comment":
                                documentation.comments.extend(processed.matches)
                            
                            # Extract TODOs
                            elif pattern["name"] in ["todo", "fixme", "note", "warning"]:
                                documentation.todos.extend(processed.matches)
                            
                            # Extract metadata
                            elif pattern["name"] == "metadata":
                                for item in processed.matches:
                                    if "key" in item and "value" in item:
                                        documentation.metadata[item["key"]] = item["value"]
                            
                            # Update pattern stats with success
                            await self._update_pattern_stats(
                                pattern["name"],
                                True,
                                extraction_time,
                                len(processed.matches)
                            )
                            
                    except Exception as e:
                        extraction_time = time.time() - start_time
                        # Update pattern stats with failure
                        await self._update_pattern_stats(
                            pattern["name"],
                            False,
                            extraction_time,
                            0
                        )
                        await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                        continue
                        
        except Exception as e:
            await log(f"Error extracting documentation: {e}", level="error")
            
        return documentation
    
    async def _extract_metrics(self, ast: Dict[str, Any]) -> ComplexityMetrics:
        """Extract complexity metrics from AST."""
        metrics = ComplexityMetrics()
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            # Get patterns for metrics category
            patterns = await pattern_processor.get_patterns_for_category(
                FeatureCategory.METRICS,
                PatternPurpose.UNDERSTANDING,
                self.language_id,
                self.parser_type
            )
            
            if patterns:
                for pattern in patterns:
                    # Check if pattern should be used
                    if not await self._should_use_pattern(pattern["name"]):
                        continue
                    
                    start_time = time.time()
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            ast,
                            self.language_id
                        )
                        
                        extraction_time = time.time() - start_time
                        
                        if processed.matches:
                            # Update metrics based on pattern type
                            if pattern["name"] == "cyclomatic":
                                metrics.cyclomatic = len(processed.matches)
                            elif pattern["name"] == "cognitive":
                                metrics.cognitive = len(processed.matches)
                            elif pattern["name"] == "lines_of_code":
                                metrics.lines_of_code = processed.matches[0]
                            
                            # Update pattern stats with success
                            await self._update_pattern_stats(
                                pattern["name"],
                                True,
                                extraction_time,
                                len(processed.matches)
                            )
                            
                    except Exception as e:
                        extraction_time = time.time() - start_time
                        # Update pattern stats with failure
                        await self._update_pattern_stats(
                            pattern["name"],
                            False,
                            extraction_time,
                            0
                        )
                        await log(f"Error processing pattern {pattern['name']}: {e}", level="warning")
                        continue
                        
        except Exception as e:
            await log(f"Error extracting metrics: {e}", level="error")
            
        return metrics
    
    async def _extract_features_chunked(self, ast: Dict[str, Any], source_code: str) -> ExtractedFeatures:
        """Extract features from large files by processing in chunks."""
        CHUNK_SIZE = 100 * 1024  # 100KB chunks
        features = ExtractedFeatures()
        
        # Split source code into chunks
        chunks = [source_code[i:i + CHUNK_SIZE] 
                 for i in range(0, len(source_code), CHUNK_SIZE)]
        
        for i, chunk in enumerate(chunks):
            try:
                # Process each chunk
                chunk_features = await self._extract_chunk_features(chunk, i)
                
                # Merge features
                for category, category_features in chunk_features.items():
                    if category not in features.features:
                        features.features[category] = {}
                    features.features[category].update(category_features)
                    
            except Exception as e:
                await log(f"Error processing chunk {i}: {e}", level="warning")
                continue
        
        return features
    
    async def _extract_chunk_features(self, chunk: str, chunk_index: int) -> Dict[str, Any]:
        """Extract features from a single chunk of source code."""
        features = {}
        
        try:
            # Get pattern processor instance
            from parsers.pattern_processor import pattern_processor
            
            for category in FeatureCategory:
                patterns = await pattern_processor.get_patterns_for_category(
                    category,
                    PatternPurpose.UNDERSTANDING,
                    self.language_id,
                    self.parser_type
                )
                
                category_features = {}
                for pattern in patterns:
                    # Check if pattern should be used
                    if not await self._should_use_pattern(pattern["name"]):
                        continue
                    
                    start_time = time.time()
                    try:
                        # Process pattern
                        processed = await pattern_processor.process_pattern(
                            pattern["name"],
                            chunk,
                            self.language_id
                        )
                        
                        extraction_time = time.time() - start_time
                        
                        if processed.matches:
                            # Adjust match positions for chunk index
                            for match in processed.matches:
                                if "start" in match:
                                    match["start"] += chunk_index * len(chunk)
                                if "end" in match:
                                    match["end"] += chunk_index * len(chunk)
                            category_features[pattern["name"]] = processed.matches
                            
                            # Update pattern stats with success
                            await self._update_pattern_stats(
                                pattern["name"],
                                True,
                                extraction_time,
                                len(processed.matches)
                            )
                            
                    except Exception as e:
                        extraction_time = time.time() - start_time
                        # Update pattern stats with failure
                        await self._update_pattern_stats(
                            pattern["name"],
                            False,
                            extraction_time,
                            0
                        )
                        await log(f"Error processing pattern {pattern['name']} in chunk {chunk_index}: {e}", level="warning")
                        continue
                
                if category_features:
                    features[category] = category_features
                    
        except Exception as e:
            await log(f"Error extracting features from chunk {chunk_index}: {e}", level="error")
            
        return features
    
    async def _update_pattern_stats(
        self,
        pattern_name: str,
        success: bool,
        extraction_time: float,
        features_found: int
    ) -> None:
        """Update pattern usage statistics for learning."""
        if not self._learning_enabled:
            return
            
        if pattern_name not in self._pattern_usage_stats:
            self._pattern_usage_stats[pattern_name] = {
                "uses": 0,
                "successes": 0,
                "failures": 0,
                "avg_time": 0.0,
                "features_found": 0
            }
        
        stats = self._pattern_usage_stats[pattern_name]
        stats["uses"] += 1
        if success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
        
        # Update moving averages
        stats["avg_time"] = (stats["avg_time"] * (stats["uses"] - 1) + extraction_time) / stats["uses"]
        stats["features_found"] = (stats["features_found"] * (stats["uses"] - 1) + features_found) / stats["uses"]
        
        # Update success rate
        self._pattern_success_rates[pattern_name] = stats["successes"] / stats["uses"]
        
        # Adjust thresholds based on pattern performance
        if stats["uses"] > 100:  # Wait for sufficient data
            if self._pattern_success_rates[pattern_name] < 0.3:  # Low success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 0.8,  # Reduce time allowance
                    "min_features": stats["features_found"] * 1.2  # Require more features
                }
            elif self._pattern_success_rates[pattern_name] > 0.8:  # High success rate
                self._adaptive_thresholds[pattern_name] = {
                    "max_time": stats["avg_time"] * 1.2,  # Allow more time
                    "min_features": stats["features_found"] * 0.8  # Accept fewer features
                }
    
    async def _should_use_pattern(self, pattern_name: str) -> bool:
        """Determine if a pattern should be used based on its performance."""
        if not self._learning_enabled or pattern_name not in self._pattern_success_rates:
            return True
            
        success_rate = self._pattern_success_rates[pattern_name]
        if success_rate < 0.2:  # Very poor performance
            return False
            
        return True
    
    async def _cleanup_cache(self) -> None:
        """Clean up expired cache entries and manage memory usage."""
        try:
            current_time = time.time()
            
            # Only run cleanup at configured intervals
            if current_time - self._last_cleanup < self._cache_config["cleanup_interval"]:
                return
                
            self._last_cleanup = current_time
            
            # Get current memory usage
            process = psutil.Process()
            memory_info = process.memory_info()
            
            # Check if we need to clean up
            if memory_info.rss > self._cache_config["max_memory"]:
                # Clean up cache entries
                await cache_coordinator.cleanup(
                    f"feature_extractor_{self.language_id}",
                    max_memory=self._cache_config["max_memory"],
                    ttl=self._cache_config["ttl"]
                )
                
                # Update cache stats
                self._cache_stats.evictions += 1
                self._cache_stats.memory_usage = memory_info.rss
                
        except Exception as e:
            await log(f"Error in cache cleanup: {e}", level="error")

# Global instance cache
_extractor_instances: Dict[str, FeatureExtractor] = {}

async def get_feature_extractor(language_id: str) -> Optional[FeatureExtractor]:
    """Get a feature extractor instance.
    
    Args:
        language_id: The language to get extractor for
        
    Returns:
        Optional[FeatureExtractor]: The extractor instance or None if initialization fails
    """
    if language_id not in _extractor_instances:
        extractor = FeatureExtractor(language_id)
        if await extractor.initialize():
            _extractor_instances[language_id] = extractor
        else:
            return None
    return _extractor_instances[language_id]