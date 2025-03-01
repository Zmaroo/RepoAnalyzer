#!/usr/bin/env python3
"""
Unit tests for semantic modules.

This module tests the semantic functionality in the RepoAnalyzer project:
1. Text and code embedding
2. Vector storage and retrieval
3. Semantic search and similarity
4. Embedding caching and optimization
"""

import os
import sys
import pytest
import asyncio
import json
import numpy as np
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import semantic modules
from semantic.embeddings import (
    EmbeddingManager,
    CodeEmbedder,
    TextEmbedder
)
from semantic.vector_store import VectorStore
from semantic.similarity import (
    cosine_similarity,
    euclidean_distance,
    semantic_similarity
)
from embedding.openai_embedding import OpenAIEmbedding
from embedding.huggingface_embedding import HuggingFaceEmbedding
from embedding.local_embedding import LocalEmbedding

# Import test utils
from utils.testing_utils import (
    sample_code_snippet,
    sample_text_snippet
)


class TestEmbeddingModels:
    """Test various embedding models."""
    
    @pytest.fixture
    def sample_text(self):
        """Sample text for embedding tests."""
        return "This is a sample text for testing embeddings."
    
    @pytest.fixture
    def sample_code(self):
        """Sample code for embedding tests."""
        return """
        def hello_world():
            print("Hello, world!")
            return 42
        """
    
    @pytest.mark.asyncio
    async def test_openai_embedding(self, sample_text):
        """Test OpenAI embedding generation."""
        # Mock the OpenAI API response
        mock_response = MagicMock()
        mock_response.data = [{"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}]
        
        # Patch the OpenAI client
        with patch('embedding.openai_embedding.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_client.embeddings.create.return_value = mock_response
            mock_openai.return_value = mock_client
            
            # Create the embedding model
            model = OpenAIEmbedding(api_key="fake_key", model_name="text-embedding-ada-002")
            
            # Generate embedding
            embedding = await model.get_embedding(sample_text)
            
            # Verify the embedding
            assert len(embedding) == 5
            assert embedding[0] == 0.1
            assert embedding[4] == 0.5
            
            # Verify the API was called correctly
            mock_client.embeddings.create.assert_called_once()
            call_args = mock_client.embeddings.create.call_args[1]
            assert call_args["model"] == "text-embedding-ada-002"
            assert call_args["input"] == sample_text
    
    @pytest.mark.asyncio
    async def test_huggingface_embedding(self, sample_text):
        """Test HuggingFace embedding generation."""
        # Create a mock embedding tensor
        mock_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
        
        # Patch the transformer pipeline
        with patch('embedding.huggingface_embedding.pipeline') as mock_pipeline:
            mock_model = MagicMock()
            mock_model.return_value = [{'embedding': mock_embedding}]
            mock_pipeline.return_value = mock_model
            
            # Create the embedding model
            model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            
            # Generate embedding
            embedding = await model.get_embedding(sample_text)
            
            # Verify the embedding
            assert len(embedding) == 5
            assert embedding[0] == 0.1
            assert embedding[4] == 0.5
            
            # Verify the model was called
            mock_model.assert_called_once_with(sample_text)
    
    @pytest.mark.asyncio
    async def test_local_embedding(self, sample_text):
        """Test local embedding generation."""
        # Create a mock embedding generator
        mock_generator = AsyncMock()
        mock_generator.get_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Create the embedding model
        model = LocalEmbedding(embedding_generator=mock_generator)
        
        # Generate embedding
        embedding = await model.get_embedding(sample_text)
        
        # Verify the embedding
        assert len(embedding) == 5
        assert embedding[0] == 0.1
        assert embedding[4] == 0.5
        
        # Verify the generator was called
        mock_generator.get_embedding.assert_called_once_with(sample_text)


class TestEmbeddingManager:
    """Test the embedding manager."""
    
    @pytest.fixture
    def embedding_manager(self):
        """Create an embedding manager for testing."""
        # Create mock embedders
        text_embedder = MagicMock()
        code_embedder = MagicMock()
        
        # Setup the text embedder
        text_embedder.get_embedding.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Setup the code embedder
        code_embedder.get_embedding.return_value = [0.5, 0.4, 0.3, 0.2, 0.1]
        
        # Create the manager
        manager = EmbeddingManager(
            text_embedder=text_embedder,
            code_embedder=code_embedder
        )
        
        return manager
    
    @pytest.mark.asyncio
    async def test_text_embedding(self, embedding_manager):
        """Test text embedding through the manager."""
        text = "This is a sample text."
        
        # Get the embedding
        embedding = await embedding_manager.get_text_embedding(text)
        
        # Verify the embedding
        assert len(embedding) == 5
        assert embedding[0] == 0.1
        assert embedding[4] == 0.5
        
        # Verify the text embedder was called
        embedding_manager.text_embedder.get_embedding.assert_called_once_with(text)
    
    @pytest.mark.asyncio
    async def test_code_embedding(self, embedding_manager):
        """Test code embedding through the manager."""
        code = "def test(): return True"
        
        # Get the embedding
        embedding = await embedding_manager.get_code_embedding(code)
        
        # Verify the embedding
        assert len(embedding) == 5
        assert embedding[0] == 0.5
        assert embedding[4] == 0.1
        
        # Verify the code embedder was called
        embedding_manager.code_embedder.get_embedding.assert_called_once_with(code)
    
    @pytest.mark.asyncio
    async def test_embedding_caching(self, embedding_manager):
        """Test that embeddings are cached."""
        text = "This is a sample text."
        
        # Get the embedding twice
        embedding1 = await embedding_manager.get_text_embedding(text)
        embedding2 = await embedding_manager.get_text_embedding(text)
        
        # Verify the embeddings are the same
        assert embedding1 == embedding2
        
        # Verify the text embedder was called only once
        embedding_manager.text_embedder.get_embedding.assert_called_once_with(text)


class TestVectorStore:
    """Test the vector store."""
    
    @pytest.fixture
    def vector_store(self):
        """Create a vector store for testing."""
        # Create a mock storage backend
        mock_backend = MagicMock()
        
        # Setup the mock backend
        mock_backend.store_vector.return_value = "vector_id_1"
        mock_backend.get_vector.return_value = ([0.1, 0.2, 0.3, 0.4, 0.5], {"metadata": "test"})
        mock_backend.search_vectors.return_value = [
            ("vector_id_1", 0.95, {"metadata": "test1"}),
            ("vector_id_2", 0.85, {"metadata": "test2"})
        ]
        
        # Create the vector store
        store = VectorStore(storage_backend=mock_backend)
        
        return store
    
    @pytest.mark.asyncio
    async def test_store_vector(self, vector_store):
        """Test storing a vector."""
        # Setup
        vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        metadata = {"text": "Sample text", "source": "test"}
        
        # Store the vector
        vector_id = await vector_store.store(vector, metadata)
        
        # Verify the ID
        assert vector_id == "vector_id_1"
        
        # Verify the backend was called
        vector_store.storage_backend.store_vector.assert_called_once_with(vector, metadata)
    
    @pytest.mark.asyncio
    async def test_retrieve_vector(self, vector_store):
        """Test retrieving a vector."""
        # Setup
        vector_id = "vector_id_1"
        
        # Retrieve the vector
        vector, metadata = await vector_store.get(vector_id)
        
        # Verify the vector and metadata
        assert len(vector) == 5
        assert vector[0] == 0.1
        assert metadata["metadata"] == "test"
        
        # Verify the backend was called
        vector_store.storage_backend.get_vector.assert_called_once_with(vector_id)
    
    @pytest.mark.asyncio
    async def test_search_vectors(self, vector_store):
        """Test searching for similar vectors."""
        # Setup
        query_vector = [0.1, 0.2, 0.3, 0.4, 0.5]
        
        # Search for similar vectors
        results = await vector_store.search(query_vector, top_k=2)
        
        # Verify the results
        assert len(results) == 2
        assert results[0][0] == "vector_id_1"
        assert results[0][1] == 0.95
        assert results[0][2]["metadata"] == "test1"
        
        # Verify the backend was called
        vector_store.storage_backend.search_vectors.assert_called_once_with(query_vector, 2)


class TestSimilarityFunctions:
    """Test similarity functions."""
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        # Setup
        vec1 = np.array([1, 0, 0, 0])
        vec2 = np.array([0, 1, 0, 0])
        vec3 = np.array([1, 1, 0, 0])
        
        # Calculate similarities
        sim1_2 = cosine_similarity(vec1, vec2)
        sim1_3 = cosine_similarity(vec1, vec3)
        sim2_3 = cosine_similarity(vec2, vec3)
        
        # Verify similarities
        assert sim1_2 == 0  # Orthogonal vectors
        assert sim1_3 > 0 and sim1_3 < 1  # Somewhat similar
        assert sim2_3 > 0 and sim2_3 < 1  # Somewhat similar
        assert sim1_3 == sim2_3  # Symmetric similarity
    
    def test_euclidean_distance(self):
        """Test euclidean distance calculation."""
        # Setup
        vec1 = np.array([0, 0, 0])
        vec2 = np.array([1, 0, 0])
        vec3 = np.array([1, 1, 0])
        
        # Calculate distances
        dist1_2 = euclidean_distance(vec1, vec2)
        dist1_3 = euclidean_distance(vec1, vec3)
        dist2_3 = euclidean_distance(vec2, vec3)
        
        # Verify distances
        assert dist1_2 == 1  # Unit distance
        assert dist1_3 == np.sqrt(2)  # Diagonal distance
        assert dist2_3 == 1  # Unit distance
    
    def test_semantic_similarity(self):
        """Test semantic similarity calculation."""
        # Setup
        vec1 = np.array([0.5, 0.5, 0.5, 0.5])
        vec2 = np.array([0.1, 0.1, 0.1, 0.1])
        
        # Calculate similarity
        similarity = semantic_similarity(vec1, vec2)
        
        # Verify similarity
        assert 0 <= similarity <= 1  # Similarity should be normalized 