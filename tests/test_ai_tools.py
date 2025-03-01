#!/usr/bin/env python3
"""
Unit tests for the AI tools module.

This module tests the core functionality of the AI tools components:
1. AIAssistant interface
2. Reference repository learning
3. Code understanding
4. Graph capabilities
"""

import os
import sys
import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the AI tools modules
from ai_tools.ai_interface import AIAssistant
from ai_tools.reference_repository_learning import (
    ReferenceRepoLearning,
    PatternLearningResult
)
from ai_tools.code_understanding import CodeUnderstanding
from ai_tools.graph_capabilities import GraphAnalysis

# Import related modules needed for testing
from parsers.types import ParserResult, FileType, ParserType, Documentation
from parsers.models import FileMetadata, PatternMatch, PatternDefinition
from utils.error_handling import ProcessingError, AsyncErrorBoundary

class TestAIAssistant:
    """Test the AIAssistant interface."""
    
    @pytest.mark.asyncio
    async def test_initialization(self):
        """Test AIAssistant initialization."""
        assistant = AIAssistant()
        assert assistant is not None
        assert hasattr(assistant, 'code_understanding')
        assert hasattr(assistant, 'graph_analysis')
        assert hasattr(assistant, 'reference_learning')
        
        # Cleanup
        assistant.close()
    
    @pytest.mark.asyncio
    @patch('ai_tools.code_understanding.CodeUnderstanding.get_code_context')
    async def test_get_code_context(self, mock_get_context):
        """Test getting code context."""
        # Setup mock
        mock_result = {
            "context": "Sample code context",
            "related_files": ["file1.py", "file2.py"],
            "imports": ["module1", "module2"]
        }
        mock_get_context.return_value = mock_result
        
        # Test the method
        assistant = AIAssistant()
        result = await assistant.get_code_context(repo_id=1, file_path="test.py")
        
        # Verify
        assert result == mock_result
        mock_get_context.assert_called_once_with(repo_id=1, file_path="test.py")
        
        # Cleanup
        assistant.close()
    
    @pytest.mark.asyncio
    @patch('ai_tools.reference_repository_learning.ReferenceRepoLearning.learn_from_repository')
    async def test_learn_from_reference_repo(self, mock_learn):
        """Test learning from reference repository."""
        # Setup mock
        mock_result = PatternLearningResult(
            patterns_found=10,
            best_practices=5,
            documentation_patterns=3,
            metrics={"code_quality": 0.8}
        )
        mock_learn.return_value = mock_result
        
        # Test the method
        assistant = AIAssistant()
        result = await assistant.learn_from_reference_repo(repo_id=1)
        
        # Verify
        assert result.patterns_found == 10
        assert result.best_practices == 5
        mock_learn.assert_called_once_with(repo_id=1)
        
        # Cleanup
        assistant.close()

class TestReferenceRepoLearning:
    """Test the Reference Repository Learning component."""
    
    @pytest.mark.asyncio
    @patch('db.neo4j_ops.run_query')
    @patch('db.psql.query')
    async def test_extract_patterns(self, mock_psql, mock_neo4j):
        """Test extracting patterns from a repository."""
        # Setup mocks
        mock_psql.return_value = [
            {"id": 1, "file_path": "test.py", "language_id": "python"},
            {"id": 2, "file_path": "README.md", "language_id": "markdown"}
        ]
        
        # Initialize the component
        learning = ReferenceRepoLearning()
        
        # Mocking the internal methods
        with patch.object(learning, '_extract_code_patterns') as mock_extract_code:
            mock_extract_code.return_value = {"code_patterns": 5}
            
            # Call the method
            result = await learning.extract_patterns(repo_id=1)
            
            # Verify
            assert result is not None
            mock_psql.assert_called_once()
            mock_extract_code.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_find_similar_patterns(self):
        """Test finding similar patterns between repositories."""
        # Setup
        learning = ReferenceRepoLearning()
        
        # Mocking the database queries
        with patch('db.psql.query') as mock_query:
            mock_query.return_value = [
                {"id": 1, "pattern_name": "ErrorHandling", "category": "best_practice"},
                {"id": 2, "pattern_name": "DocumentationStyle", "category": "documentation"}
            ]
            
            # Call the method
            patterns = await learning.find_similar_patterns(
                source_repo_id=1,
                target_repo_id=2,
                similarity_threshold=0.7
            )
            
            # Verify
            assert len(patterns) == 2
            mock_query.assert_called()

class TestCodeUnderstanding:
    """Test the Code Understanding component."""
    
    @pytest.mark.asyncio
    async def test_analyze_code_snippets(self):
        """Test code snippet analysis."""
        # Setup
        understanding = CodeUnderstanding()
        
        # Mock the embedding model
        with patch('embedding.embedding_models.code_embedder.embed_code') as mock_embed:
            mock_embed.return_value = [0.1, 0.2, 0.3]  # Sample embedding
            
            # Test with a simple code snippet
            result = await understanding.analyze_code_snippets(
                ["def hello_world():\n    print('Hello, World!')"],
                language="python"
            )
            
            # Verify
            assert result is not None
            mock_embed.assert_called_once()

class TestGraphAnalysis:
    """Test the Graph Analysis component."""
    
    @pytest.mark.asyncio
    @patch('db.neo4j_ops.run_query')
    async def test_analyze_code_structure(self, mock_run_query):
        """Test code structure analysis."""
        # Setup
        mock_run_query.return_value = {
            "nodes": 50,
            "relationships": 120,
            "metrics": {
                "complexity": 0.7,
                "modularity": 0.8
            }
        }
        
        # Initialize and test
        analysis = GraphAnalysis()
        result = await analysis.analyze_code_structure(repo_id=1)
        
        # Verify
        assert result is not None
        assert "metrics" in result
        assert result["metrics"]["complexity"] == 0.7
        mock_run_query.assert_called_once() 