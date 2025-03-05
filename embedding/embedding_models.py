"""Unified embedding models for code and documentation."""

import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import Union, Optional, Set
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from parsers.models import FileType, FileClassification  # Add imports from models
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary
)
import asyncio

# Create cache instance
embedding_cache = UnifiedCache("embeddings", ttl=7200)

# Register cache asynchronously - will be done when the module is used
async def initialize():
    """Initialize the embedding models module."""
    await cache_coordinator.register_cache("embeddings", embedding_cache)

class BaseEmbedder:
    """Base class for embedding models."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self.model_name = None
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.tokenizer = None
        self.model = None
        self._cache = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("Embedder not initialized. Use create() to initialize.")
        if not self.model:
            raise ProcessingError("Model not initialized")
        if not self.tokenizer:
            raise ProcessingError("Tokenizer not initialized")
        if not self._cache:
            raise ProcessingError("Cache not initialized")
        return True
    
    @classmethod
    async def create(cls, model_name: str) -> 'BaseEmbedder':
        """Async factory method to create and initialize an embedder."""
        instance = cls()
        instance.model_name = model_name
        
        try:
            async with AsyncErrorBoundary(
                operation_name=f"{model_name} embedder initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize model and tokenizer
                instance.tokenizer = AutoTokenizer.from_pretrained(model_name)
                instance.model = AutoModel.from_pretrained(model_name).to(instance.device)
                instance.model.eval()
                
                # Initialize cache
                instance._cache = UnifiedCache(f"embeddings_{model_name}", ttl=7200)
                await cache_coordinator.register_cache(f"embeddings_{model_name}", instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component(f"embedder_{model_name}")
                
                instance._initialized = True
                await log(f"{model_name} embedder initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing {model_name} embedder: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize {model_name} embedder: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def _compute_embedding(self, text: str) -> np.ndarray:
        """Compute embedding for text."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("embedding computation"):
            async with self._lock:
                inputs = self.tokenizer(
                    text,
                    padding=True,
                    truncation=True,
                    max_length=512,
                    return_tensors="pt"
                ).to(self.device)
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                
                return outputs.last_hidden_state[:, 0, :].cpu().numpy()
    
    @handle_async_errors(error_types=ProcessingError)
    async def embed_async(self, text: str) -> Optional[np.ndarray]:
        """Compute embedding asynchronously with caching."""
        if not self._initialized:
            await self.ensure_initialized()
            
        cache_key = f"{self.__class__.__name__}:{hash(text)}"
        
        # Check cache
        task = asyncio.create_task(self._cache.get_async(cache_key))
        self._pending_tasks.add(task)
        try:
            cached = await task
            if cached is not None:
                return np.array(cached)
        finally:
            self._pending_tasks.remove(task)
        
        # Compute new embedding
        task = asyncio.create_task(self._compute_embedding(text))
        self._pending_tasks.add(task)
        try:
            embedding = await task
        finally:
            self._pending_tasks.remove(task)
        
        # Cache result
        task = asyncio.create_task(self._cache.set_async(cache_key, embedding.tolist()))
        self._pending_tasks.add(task)
        try:
            await task
        finally:
            self._pending_tasks.remove(task)
        
        return embedding
    
    async def cleanup(self):
        """Clean up model resources."""
        try:
            if not self._initialized:
                return
                
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clean up cache
            if self._cache:
                await cache_coordinator.unregister_cache(f"embeddings_{self.model_name}")
                self._cache = None
            
            # Clean up model resources
            if self.model:
                del self.model
            if self.tokenizer:
                del self.tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component(f"embedder_{self.model_name}")
            
            self._initialized = False
            await log(f"{self.model_name} embedder cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up {self.model_name} embedder: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup {self.model_name} embedder: {e}")

class CodeEmbedder(BaseEmbedder):
    """Code-specific embedding model using GraphCodeBERT."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
    
    @classmethod
    async def create(cls) -> 'CodeEmbedder':
        """Async factory method to create and initialize a CodeEmbedder."""
        return await super().create('microsoft/graphcodebert-base')
    
    async def embed_code(self, code: str) -> Optional[np.ndarray]:
        """Alias for embed_async to maintain compatibility with tests."""
        return await self.embed_async(code)

class DocEmbedder(BaseEmbedder):
    """Documentation-specific embedding model."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
    
    @classmethod
    async def create(cls) -> 'DocEmbedder':
        """Async factory method to create and initialize a DocEmbedder."""
        return await super().create('sentence-transformers/all-mpnet-base-v2')

# Global instances - these need to be initialized before use
_code_embedder = None
_doc_embedder = None

async def init_embedders():
    """Initialize the global embedder instances."""
    global _code_embedder, _doc_embedder
    
    try:
        async with AsyncErrorBoundary("embedder initialization"):
            # Initialize code embedder
            _code_embedder = await CodeEmbedder.create()
            
            # Initialize doc embedder
            _doc_embedder = await DocEmbedder.create()
            
            await log("Embedders initialized", level="info")
    except Exception as e:
        await log(f"Error initializing embedders: {e}", level="error")
        raise ProcessingError(f"Failed to initialize embedders: {e}")

# Export with proper async handling
async def get_code_embedder() -> CodeEmbedder:
    """Get the code embedder instance.
    
    Returns:
        CodeEmbedder: The singleton code embedder instance
    """
    global _code_embedder
    if not _code_embedder:
        _code_embedder = await CodeEmbedder.create()
    return _code_embedder

async def get_doc_embedder() -> DocEmbedder:
    """Get the doc embedder instance.
    
    Returns:
        DocEmbedder: The singleton doc embedder instance
    """
    global _doc_embedder
    if not _doc_embedder:
        _doc_embedder = await DocEmbedder.create()
    return _doc_embedder
