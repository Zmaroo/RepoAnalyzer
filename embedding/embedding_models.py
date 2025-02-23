"""Unified embedding models for code and documentation."""

import torch
from transformers import AutoTokenizer, AutoModel
import numpy as np
from typing import Union, Optional
from utils.logger import log
from utils.cache import create_cache
from parsers.models import FileType, FileClassification  # Add imports from models
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    ErrorBoundary,
    AsyncErrorBoundary
)

# Create cache instances
embedding_cache = create_cache("embeddings", ttl=7200)

class BaseEmbedder:
    """Base class for embedding models."""
    
    def __init__(self, model_name: str):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        
        with ErrorBoundary("model initialization", error_types=ProcessingError):
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModel.from_pretrained(model_name).to(self.device)
            self.model.eval()
    
    @handle_errors(error_types=ProcessingError)
    def _compute_embedding(self, text: str) -> np.ndarray:
        """Compute embedding for text."""
        with ErrorBoundary("embedding computation"):
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
        cache_key = f"{self.__class__.__name__}:{hash(text)}"
        
        # Check cache
        cached = await embedding_cache.get_async(cache_key)
        if cached is not None:
            return np.array(cached)
        
        # Compute new embedding
        embedding = self._compute_embedding(text)
        
        # Cache result
        await embedding_cache.set_async(cache_key, embedding.tolist())
        
        return embedding
    
    @handle_errors(error_types=ProcessingError)
    def cleanup(self):
        """Clean up model resources."""
        with ErrorBoundary("model cleanup"):
            del self.model
            del self.tokenizer
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

class CodeEmbedder(BaseEmbedder):
    """Code-specific embedding model using GraphCodeBERT."""
    
    def __init__(self):
        super().__init__('microsoft/graphcodebert-base')

class DocEmbedder(BaseEmbedder):
    """Documentation-specific embedding model."""
    
    def __init__(self):
        super().__init__('sentence-transformers/all-mpnet-base-v2')

# Global instances
code_embedder = CodeEmbedder()
doc_embedder = DocEmbedder()
