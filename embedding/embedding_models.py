"""Embedding models with pattern-aware and context-sensitive capabilities.

This module provides embedding generation for code, documentation, and patterns,
with support for context-sensitive analysis and pattern similarity.
"""

import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import Union, Optional, Set, List, Dict, Any
from utils.logger import log
from utils.cache import UnifiedCache, cache_coordinator
from parsers.models import FileType, FileClassification  # Add imports from models
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    AsyncErrorBoundary,
    ErrorSeverity
)
import asyncio
from utils.async_runner import submit_async_task

# Initialize cache for embeddings
embedding_cache = UnifiedCache("embeddings", ttl=3600)

# Register cache asynchronously - will be done when the module is used
async def initialize():
    """Initialize the embedding models module."""
    await cache_coordinator.register_cache("embeddings", embedding_cache)

class PatternAwareEmbedder:
    """Base class for pattern-aware embedding generation."""
    
    def __init__(self):
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._context_window = 1000  # Default context window size
        self._pattern_cache = {}
    
    async def initialize(self):
        """Initialize the embedder."""
        if not self._initialized:
            # Initialize model and resources
            self._initialized = True
            log("Pattern-aware embedder initialized", level="info")
    
    async def embed_with_context(
        self,
        text: str,
        context: Optional[Dict[str, Any]] = None,
        pattern_type: Optional[str] = None
    ) -> List[float]:
        """Generate embeddings with contextual information."""
        if not self._initialized:
            await self.initialize()
        
        # Include context in embedding generation
        if context:
            text = self._enrich_with_context(text, context)
        
        # Apply pattern-specific processing
        if pattern_type:
            text = self._apply_pattern_processing(text, pattern_type)
        
        # Generate base embedding
        embedding = await self._generate_base_embedding(text)
        
        # Enhance with pattern information if available
        if pattern_type:
            embedding = await self._enhance_with_pattern(embedding, pattern_type)
        
        return embedding
    
    def _enrich_with_context(self, text: str, context: Dict[str, Any]) -> str:
        """Enrich text with contextual information."""
        enriched = text
        
        if context.get("file_path"):
            enriched = f"File: {context['file_path']}\n{enriched}"
        
        if context.get("language"):
            enriched = f"Language: {context['language']}\n{enriched}"
        
        if context.get("dependencies"):
            deps = ", ".join(context["dependencies"])
            enriched = f"Dependencies: {deps}\n{enriched}"
        
        return enriched
    
    def _apply_pattern_processing(self, text: str, pattern_type: str) -> str:
        """Apply pattern-specific text processing."""
        # Add pattern-specific markers and structure
        if pattern_type == "code_pattern":
            return f"[CODE_PATTERN]\n{text}\n[/CODE_PATTERN]"
        elif pattern_type == "doc_pattern":
            return f"[DOC_PATTERN]\n{text}\n[/DOC_PATTERN]"
        elif pattern_type == "arch_pattern":
            return f"[ARCH_PATTERN]\n{text}\n[/ARCH_PATTERN]"
        return text
    
    async def _enhance_with_pattern(
        self,
        base_embedding: List[float],
        pattern_type: str
    ) -> List[float]:
        """Enhance embedding with pattern-specific information."""
        # Apply pattern-specific enhancement
        # This is a placeholder - actual implementation would depend on the model
        return base_embedding

class CodeEmbedder(PatternAwareEmbedder):
    """Code-specific embedder with pattern awareness."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
    
    @classmethod
    async def create(cls) -> 'CodeEmbedder':
        """Async factory method to create and initialize a CodeEmbedder."""
        instance = cls()
        
        try:
            async with AsyncErrorBoundary(
                operation_name="CodeEmbedder initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize model and tokenizer
                instance.tokenizer = AutoTokenizer.from_pretrained('microsoft/graphcodebert-base')
                instance.model = AutoModel.from_pretrained('microsoft/graphcodebert-base').to(torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
                instance.model.eval()
                
                # Initialize cache
                instance._cache = UnifiedCache(f"embeddings_microsoft_graphcodebert-base", ttl=7200)
                await cache_coordinator.register_cache(f"embeddings_microsoft_graphcodebert-base", instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component(f"embedder_microsoft_graphcodebert-base")
                
                instance._initialized = True
                await log("CodeEmbedder initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing CodeEmbedder: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize CodeEmbedder: {e}")
    
    async def embed_code(
        self,
        code: str,
        language: str,
        context: Optional[Dict[str, Any]] = None,
        pattern_type: Optional[str] = None
    ) -> List[float]:
        """Generate code embeddings with pattern awareness."""
        # Add language-specific context
        if context is None:
            context = {}
        context["language"] = language
        
        return await self.embed_with_context(code, context, pattern_type)
    
    async def embed_pattern(
        self,
        pattern: Dict[str, Any]
    ) -> List[float]:
        """Generate embeddings for code patterns."""
        context = {
            "pattern_type": pattern["type"],
            "language": pattern.get("language"),
            "complexity": pattern.get("complexity"),
            "dependencies": pattern.get("dependencies", [])
        }
        
        return await self.embed_with_context(
            pattern["content"],
            context,
            pattern_type="code_pattern"
        )
    
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
                await cache_coordinator.unregister_cache(f"embeddings_microsoft_graphcodebert-base")
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
            global_health_monitor.unregister_component(f"embedder_microsoft_graphcodebert-base")
            
            self._initialized = False
            await log("CodeEmbedder cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up CodeEmbedder: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup CodeEmbedder: {e}")

class DocEmbedder(PatternAwareEmbedder):
    """Documentation-specific embedder with pattern awareness."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        super().__init__()
    
    @classmethod
    async def create(cls) -> 'DocEmbedder':
        """Async factory method to create and initialize a DocEmbedder."""
        instance = cls()
        
        try:
            async with AsyncErrorBoundary(
                operation_name="DocEmbedder initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize model and tokenizer
                instance.tokenizer = AutoTokenizer.from_pretrained('sentence-transformers/all-mpnet-base-v2')
                instance.model = AutoModel.from_pretrained('sentence-transformers/all-mpnet-base-v2').to(torch.device('cuda' if torch.cuda.is_available() else 'cpu'))
                instance.model.eval()
                
                # Initialize cache
                instance._cache = UnifiedCache(f"embeddings_sentence-transformers_all-mpnet-base-v2", ttl=7200)
                await cache_coordinator.register_cache(f"embeddings_sentence-transformers_all-mpnet-base-v2", instance._cache)
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component(f"embedder_sentence-transformers_all-mpnet-base-v2")
                
                instance._initialized = True
                await log("DocEmbedder initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing DocEmbedder: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize DocEmbedder: {e}")
    
    async def embed_doc(
        self,
        text: str,
        doc_type: str,
        context: Optional[Dict[str, Any]] = None,
        pattern_type: Optional[str] = None
    ) -> List[float]:
        """Generate documentation embeddings with pattern awareness."""
        if context is None:
            context = {}
        context["doc_type"] = doc_type
        
        return await self.embed_with_context(text, context, pattern_type)
    
    async def embed_pattern(
        self,
        pattern: Dict[str, Any]
    ) -> List[float]:
        """Generate embeddings for documentation patterns."""
        context = {
            "pattern_type": pattern["type"],
            "doc_type": pattern.get("doc_type"),
            "structure": pattern.get("structure")
        }
        
        return await self.embed_with_context(
            pattern["content"],
            context,
            pattern_type="doc_pattern"
        )
    
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
                await cache_coordinator.unregister_cache(f"embeddings_sentence-transformers_all-mpnet-base-v2")
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
            global_health_monitor.unregister_component(f"embedder_sentence-transformers_all-mpnet-base-v2")
            
            self._initialized = False
            await log("DocEmbedder cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up DocEmbedder: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup DocEmbedder: {e}")

class ArchitectureEmbedder(PatternAwareEmbedder):
    """Architecture-specific embedder with pattern awareness."""
    
    async def embed_architecture(
        self,
        structure: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        pattern_type: Optional[str] = None
    ) -> List[float]:
        """Generate architecture embeddings with pattern awareness."""
        # Convert structure to text representation
        text = self._structure_to_text(structure)
        
        if context is None:
            context = {}
        context["structure_type"] = structure.get("type")
        
        return await self.embed_with_context(text, context, pattern_type)
    
    def _structure_to_text(self, structure: Dict[str, Any]) -> str:
        """Convert architecture structure to text representation."""
        text_parts = []
        
        if "components" in structure:
            text_parts.append("Components:")
            for comp in structure["components"]:
                text_parts.append(f"- {comp['name']}: {comp.get('description', '')}")
        
        if "relationships" in structure:
            text_parts.append("\nRelationships:")
            for rel in structure["relationships"]:
                text_parts.append(
                    f"- {rel['source']} -> {rel['target']}: {rel.get('type', '')}"
                )
        
        return "\n".join(text_parts)
    
    async def embed_pattern(
        self,
        pattern: Dict[str, Any]
    ) -> List[float]:
        """Generate embeddings for architecture patterns."""
        context = {
            "pattern_type": pattern["type"],
            "components": len(pattern.get("components", [])),
            "relationships": len(pattern.get("relationships", []))
        }
        
        return await self.embed_with_context(
            self._structure_to_text(pattern),
            context,
            pattern_type="arch_pattern"
        )

# Global instances
code_embedder = CodeEmbedder()
doc_embedder = DocEmbedder()
arch_embedder = ArchitectureEmbedder()

async def init_embedders():
    """Initialize all embedders."""
    try:
        await asyncio.gather(
            code_embedder.initialize(),
            doc_embedder.initialize(),
            arch_embedder.initialize()
        )
        log("All embedders initialized", level="info")
    except Exception as e:
        log(f"Error initializing embedders: {e}", level="error")
        raise

# Export with proper async handling
async def get_code_embedder() -> CodeEmbedder:
    """Get the code embedder instance.
    
    Returns:
        CodeEmbedder: The singleton code embedder instance
    """
    global code_embedder
    if not code_embedder:
        code_embedder = await CodeEmbedder.create()
    return code_embedder

async def get_doc_embedder() -> DocEmbedder:
    """Get the doc embedder instance.
    
    Returns:
        DocEmbedder: The singleton doc embedder instance
    """
    global doc_embedder
    if not doc_embedder:
        doc_embedder = await DocEmbedder.create()
    return doc_embedder
