"""Vector store for semantic search and similarity matching.

This module provides a vector store for storing and searching embeddings,
with support for:
1. Similarity search
2. Pattern matching
3. Nearest neighbor search
4. Vector indexing
"""

import numpy as np
from typing import Dict, List, Optional, Any, Set
import asyncio
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    ProcessingError,
    ErrorSeverity
)
from utils.async_runner import submit_async_task
from utils.cache import UnifiedCache, cache_coordinator
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor, ComponentStatus
import time

class VectorStore:
    """Vector store for semantic search and similarity matching."""
    
    def __init__(self, index_name: str, dimension: int = 768):
        self._initialized = False
        self._index_name = index_name
        self._dimension = dimension
        self._vectors = []
        self._metadata = []
        self._pending_tasks: Set[asyncio.Task] = set()
        self._cache = None
        self._lock = asyncio.Lock()
        self._metrics = {
            "total_searches": 0,
            "successful_searches": 0,
            "failed_searches": 0,
            "search_times": []
        }
    
    @classmethod
    async def create(cls, index_name: str, dimension: int = 768) -> 'VectorStore':
        """Create and initialize a vector store."""
        instance = cls(index_name, dimension)
        await instance.initialize()
        return instance
    
    async def initialize(self):
        """Initialize the vector store."""
        if self._initialized:
            return
            
        try:
            async with AsyncErrorBoundary(
                operation_name="vector_store_initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize cache
                self._cache = UnifiedCache(f"vector_store_{self._index_name}")
                await cache_coordinator.register_cache(self._cache)
                
                # Register shutdown handler
                register_shutdown_handler(self.cleanup)
                
                # Register with health monitoring
                global_health_monitor.register_component(
                    f"vector_store_{self._index_name}",
                    health_check=self._check_health
                )
                
                self._initialized = True
                await log(f"Vector store {self._index_name} initialized", level="info")
        except Exception as e:
            await log(f"Error initializing vector store: {e}", level="error")
            raise ProcessingError(f"Failed to initialize vector store: {e}")
    
    async def add_embedding(
        self,
        vector: List[float],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an embedding to the store."""
        if not self._initialized:
            await self.initialize()
            
        if len(vector) != self._dimension:
            raise ValueError(f"Vector dimension {len(vector)} does not match store dimension {self._dimension}")
        
        async with self._lock:
            self._vectors.append(np.array(vector))
            self._metadata.append(metadata or {})
    
    async def search(
        self,
        query_vector: List[float],
        limit: int = 5,
        min_score: float = 0.7,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors."""
        if not self._initialized:
            await self.initialize()
            
        start_time = time.time()
        self._metrics["total_searches"] += 1
        
        try:
            if len(query_vector) != self._dimension:
                raise ValueError(f"Query vector dimension {len(query_vector)} does not match store dimension {self._dimension}")
            
            query_np = np.array(query_vector)
            
            # Calculate cosine similarities
            similarities = []
            for i, vec in enumerate(self._vectors):
                # Apply filters if provided
                if filter_dict and not self._matches_filter(self._metadata[i], filter_dict):
                    continue
                    
                similarity = np.dot(vec, query_np) / (np.linalg.norm(vec) * np.linalg.norm(query_np))
                if similarity >= min_score:
                    similarities.append((similarity, i))
            
            # Sort by similarity
            similarities.sort(reverse=True)
            
            # Return top results
            results = []
            for similarity, idx in similarities[:limit]:
                results.append({
                    "score": float(similarity),
                    "metadata": self._metadata[idx]
                })
            
            # Update metrics
            self._metrics["successful_searches"] += 1
            search_time = time.time() - start_time
            self._metrics["search_times"].append(search_time)
            
            # Update health status
            await global_health_monitor.update_component_status(
                f"vector_store_{self._index_name}",
                ComponentStatus.HEALTHY,
                response_time=search_time * 1000,  # Convert to ms
                error=False
            )
            
            return results
        except Exception as e:
            self._metrics["failed_searches"] += 1
            await log(f"Error searching vectors: {e}", level="error")
            
            # Update health status
            await global_health_monitor.update_component_status(
                f"vector_store_{self._index_name}",
                ComponentStatus.DEGRADED,
                error=True,
                details={"error": str(e)}
            )
            
            raise ProcessingError(f"Failed to search vectors: {e}")
    
    def _matches_filter(self, metadata: Dict[str, Any], filter_dict: Dict[str, Any]) -> bool:
        """Check if metadata matches filter criteria."""
        return all(
            key in metadata and metadata[key] == value
            for key, value in filter_dict.items()
        )
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for vector store."""
        # Calculate average search time
        avg_search_time = sum(self._metrics["search_times"]) / len(self._metrics["search_times"]) if self._metrics["search_times"] else 0
        
        # Calculate health status
        status = ComponentStatus.HEALTHY
        details = {
            "metrics": {
                "total_searches": self._metrics["total_searches"],
                "success_rate": self._metrics["successful_searches"] / self._metrics["total_searches"] if self._metrics["total_searches"] > 0 else 0,
                "vector_count": len(self._vectors),
                "avg_search_time": avg_search_time
            }
        }
        
        # Check for degraded conditions
        if details["metrics"]["success_rate"] < 0.8:
            status = ComponentStatus.DEGRADED
            details["reason"] = "Low search success rate"
        elif avg_search_time > 1.0:
            status = ComponentStatus.DEGRADED
            details["reason"] = "High search times"
        
        return {
            "status": status,
            "details": details
        }
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(self._cache)
            
            # Clear vectors and metadata
            self._vectors.clear()
            self._metadata.clear()
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component(f"vector_store_{self._index_name}")
            
            self._initialized = False
            await log(f"Vector store {self._index_name} cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up vector store: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup vector store: {e}")

# Export the class
__all__ = ['VectorStore'] 