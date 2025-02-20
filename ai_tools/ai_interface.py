"""
Unified AI Assistant Interface

This module exposes a simplified API that combines:
  • Graph analysis capabilities (for code structure and metrics).
  • Semantic search functionalities.

Important:
  - Repository indexing is handled separately in index.py (leveraging async_indexer).
  - This module does NOT serve as an entry point for indexing operations.
  - Future AI functionalities can be added here without duplicating or interfering with
    the repository indexing code.
"""

from ai_tools.graph_capabilities import GraphAnalysis
from semantic.search import semantic_search, search_code, search_docs
from utils.logger import log
from ai_tools.code_understanding import CodeUnderstanding
from semantic.search import search_available_docs, share_docs_with_repo
from typing import List, Dict, Optional, Any
from semantic.search import (
    get_repo_docs,
    create_doc_cluster,
    update_doc_version,
    search_docs,
)
from embedding.embedding_models import DocEmbedder
from sklearn.cluster import DBSCAN
from difflib import SequenceMatcher
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    AsyncErrorBoundary,
    ErrorBoundary
)
import numpy as np
import os
from config import parser_config  # Add configuration import


class AIAssistant:
    """Unified AI assistance interface."""
    
    def __init__(self):
        with ErrorBoundary("AI Assistant initialization"):
            self.graph_analysis = GraphAnalysis()
            self.code_understanding = CodeUnderstanding()
            self.doc_embedder = DocEmbedder()
            
            # Validate language data path from config
            if not os.path.exists(parser_config.language_data_path):
                raise ProcessingError(
                    f"Invalid language data path: {parser_config.language_data_path}"
                )
            # Additional AI tools can be initialized here in the future.

    @handle_async_errors(error_types=ProcessingError)
    async def analyze_repository(self, repo_id: int) -> Dict[str, Any]:
        """Perform comprehensive repository analysis."""
        async with AsyncErrorBoundary("repository analysis"):
            structure = await self.analyze_code_structure(repo_id)
            codebase = await self.code_understanding.analyze_codebase(repo_id)
            docs = self.analyze_documentation(repo_id)
            
            return {
                "structure": structure,
                "codebase": codebase,
                "documentation": docs
            }

    @handle_async_errors(error_types=ProcessingError)
    async def analyze_code_structure(
        self,
        repo_id: int,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze code structure using graph capabilities."""
        async with AsyncErrorBoundary("code structure analysis"):
            metrics = await self.graph_analysis.get_code_metrics(repo_id, file_path)
            dependencies = await self.graph_analysis.get_dependencies(repo_id, file_path)
            
            return {
                "metrics": metrics,
                "dependencies": dependencies
            }

    @handle_async_errors(error_types=ProcessingError)
    async def get_code_context(
        self,
        repo_id: int,
        file_path: str
    ) -> Dict[str, Any]:
        """Get comprehensive code context."""
        async with AsyncErrorBoundary("code context retrieval"):
            structure = await self.analyze_code_structure(repo_id, file_path)
            references = await self.graph_analysis.get_references(repo_id, file_path)
            context = await self.code_understanding.get_code_context(file_path, repo_id)
            
            return {
                "structure": structure,
                "references": references,
                "context": context
            }

    def trace_code_flow(self, entry_point: str, repo_id: int) -> list:
        """
        Traces the code flow starting from a given entry point.

        Args:
            entry_point: The start file path for code flow analysis.
            repo_id: Repository identifier.

        Returns:
            A list of code paths and their relationships.
        """
        try:
            return self.graph_analysis.trace_code_flow(entry_point, repo_id)
        except Exception as e:
            log(f"Error tracing code flow from {entry_point}: {e}", level="error")
            return []

    def search_code_snippets(self, query: str, repo_id: int, limit: int = 3) -> list:
        """Searches for code snippets matching the query using semantic search."""
        try:
            return search_code(query, repo_id=repo_id, limit=limit)
        except Exception as e:
            log(f"Error in semantic search for query '{query}': {e}", level="error")
            return []

    def search_documentation(self, query: str, repo_id: int = None) -> list[dict]:
        """Search across all available documentation."""
        return search_docs(query, repo_id)
    
    def get_available_docs(self, search_term: str, repo_id: int = None) -> list[dict]:
        """Find documentation that could be linked to a project."""
        return search_available_docs(search_term, repo_id)
    
    def share_documentation(self, doc_ids: list[int], target_repo_id: int) -> dict:
        """Share selected documentation with a target repository."""
        return share_docs_with_repo(doc_ids, target_repo_id)

    @handle_errors(error_types=ProcessingError)
    def analyze_documentation(self, repo_id: int) -> Dict[str, Any]:
        """Analyze repository documentation."""
        with ErrorBoundary("documentation analysis"):
            docs = get_repo_docs(repo_id)
            
            return {
                "total_docs": len(docs),
                "clusters": self._analyze_doc_clusters(docs),
                "coverage": self._analyze_coverage(docs),
                "quality": self._batch_quality_analysis(docs)
            }

    @handle_errors(error_types=ProcessingError)
    def _analyze_doc_clusters(self, docs: List[Dict]) -> Dict[str, Any]:
        """Cluster similar documentation."""
        with ErrorBoundary("documentation clustering"):
            if not docs:
                return {}
            
            embeddings = np.array([
                self.doc_embedder.embed(doc['content'])
                for doc in docs
            ])
            
            clustering = DBSCAN(eps=0.3, min_samples=2).fit(embeddings)
            
            clusters = {}
            for i, label in enumerate(clustering.labels_):
                if label >= 0:
                    if label not in clusters:
                        clusters[label] = []
                    clusters[label].append({
                        'id': docs[i]['id'],
                        'path': docs[i]['file_path']
                    })
            
            return clusters

    @handle_errors(error_types=ProcessingError)
    def _analyze_coverage(self, docs: List[Dict]) -> Dict[str, Any]:
        """Analyze documentation coverage."""
        with ErrorBoundary("coverage analysis"):
            coverage = {
                "total_lines": sum(len(doc['content'].splitlines()) for doc in docs),
                "coverage_by_type": {},
                "missing_areas": []
            }
            
            for doc in docs:
                doc_type = doc.get('doc_type', 'unknown')
                if doc_type not in coverage["coverage_by_type"]:
                    coverage["coverage_by_type"][doc_type] = 0
                coverage["coverage_by_type"][doc_type] += 1
            
            return coverage

    @handle_errors(error_types=ProcessingError)
    def _batch_quality_analysis(self, docs: List[Dict]) -> Dict[str, Any]:
        """Analyze documentation quality."""
        with ErrorBoundary("quality analysis"):
            quality_metrics = {}
            
            for doc in docs:
                metrics = {
                    "completeness": len(doc['content'].split()) / 100,  # Basic metric
                    "has_examples": "```" in doc['content'],
                    "has_sections": "#" in doc['content']
                }
                quality_metrics[doc['id']] = metrics
            
            return quality_metrics

    def suggest_documentation_improvements(self, repo_id: int) -> List[Dict]:
        """Suggest specific documentation improvements"""
        docs = get_repo_docs(repo_id)
        suggestions = []
        
        for doc in docs:
            quality = self._batch_quality_analysis([doc])[doc['id']]
            
            if quality['completeness'] < 0.7:
                suggestions.append({
                    "doc_id": doc['id'],
                    "type": "completeness",
                    "suggestion": "Add more detailed explanations and examples"
                })
                
            if quality['structure'] < 0.7:
                suggestions.append({
                    "doc_id": doc['id'],
                    "type": "structure",
                    "suggestion": "Improve document structure with headers and sections"
                })
                
        return suggestions

    def track_doc_version(self, doc_id: int, new_content: str) -> Dict:
        """Track new version of documentation"""
        current = self._get_current_version(doc_id)
        if current['content'] != new_content:
            changes = self._generate_diff_summary(current['content'], new_content)
            return update_doc_version(doc_id, new_content, changes)
        return current

    def suggest_documentation_links(self, repo_id: int, threshold: float = 0.8) -> List[Dict]:
        """Suggest documentation that might be relevant to the repository."""
        repo_docs = get_repo_docs(repo_id)
        all_docs = search_docs("", limit=100)  # Get broader set of docs
        
        suggestions = []
        for doc in all_docs:
            if doc['id'] not in [d['id'] for d in repo_docs]:
                relevance = self._calculate_doc_relevance(doc, repo_docs)
                if relevance > threshold:
                    suggestions.append({
                        "doc_id": doc['id'],
                        "file_path": doc['file_path'],
                        "relevance": relevance,
                        "reason": "Similar content to existing documentation"
                    })
        
        return sorted(suggestions, key=lambda x: x['relevance'], reverse=True)

    def _calculate_doc_quality(self, doc: Dict) -> Dict:
        """Calculate quality metrics for a document."""
        content = doc['content']
        return {
            "completeness": len(content.split()) / 100,  # Basic length metric
            "structure": self._analyze_doc_structure(content),
            "clarity": self._analyze_doc_clarity(content)
        }

    def _calculate_doc_relevance(self, doc: Dict, repo_docs: List[Dict]) -> float:
        """Calculate how relevant a document is to existing repo docs."""
        doc_embedding = self.doc_embedder.embed(doc['content'])
        max_similarity = 0.0
        
        for repo_doc in repo_docs:
            repo_doc_embedding = self.doc_embedder.embed(repo_doc['content'])
            similarity = self._calculate_similarity(doc_embedding, repo_doc_embedding)
            max_similarity = max(max_similarity, similarity)
            
        return max_similarity

    @handle_errors(error_types=ProcessingError)
    def close(self) -> None:
        """Clean up resources."""
        with ErrorBoundary("AI Assistant cleanup"):
            self.graph_analysis.close()
            self.code_understanding.cleanup()
            self.doc_embedder.cleanup()

# Global instance
ai_assistant = AIAssistant()