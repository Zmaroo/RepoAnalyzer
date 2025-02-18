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

from ai_tools.graph_capabilities import GraphAnalysisCapabilities
from semantic.semantic_search import search_code
from utils.logger import log
from ai_tools.code_understanding import CodeUnderstanding
from semantic.semantic_search import search_docs, search_available_docs, share_docs_with_repo
from typing import List, Dict, Optional
from indexer.doc_index import (
    get_repo_docs,
    create_doc_cluster,
    update_doc_version
)
from embedding.embedding_models import DocEmbedder
from sklearn.cluster import DBSCAN
import numpy as np
from difflib import SequenceMatcher


class AIAssistantInterface:
    """
    A unified interface for the AI assistant functionalities.

    This class wraps the graph analysis capabilities and semantic search,
    exposing a simplified API for code analysis tasks.
    """
    def __init__(self):
        self.graph_analysis = GraphAnalysisCapabilities()
        self.code_understanding = CodeUnderstanding()
        self.doc_embedder = DocEmbedder()
        # Additional AI tools can be initialized here in the future.

    def analyze_repository(self, repo_id: int) -> dict:
        """
        Performs comprehensive analysis combining graph analysis and code understanding.
        """
        try:
            # Get graph analysis results
            graph_results = self.graph_analysis.trace_code_flow("entry_point", repo_id)
            
            # Get code understanding results
            understanding_results = self.code_understanding.analyze_codebase(repo_id)
            
            return {
                "graph_analysis": graph_results,
                "code_understanding": understanding_results
            }
        except Exception as e:
            log(f"Error in repository analysis: {e}", level="error")
            return {}

    def get_code_context(self, file_path: str, repo_id: int) -> dict:
        """
        Gets comprehensive context about a code file combining:
        1. Similar code components
        2. Code relationships
        3. Semantic understanding
        """
        try:
            # Get graph-based similar components
            graph_similar = self.graph_analysis.find_similar_code(file_path, repo_id)
            
            # Get comprehensive code context
            code_context = self.code_understanding.get_code_context(file_path, repo_id)
            
            return {
                "graph_similar": graph_similar,
                "code_context": code_context
            }
        except Exception as e:
            log(f"Error getting code context: {e}", level="error")
            return {}

    def find_similar_code(self, file_path: str, repo_id: int, limit: int = 5) -> list:
        """
        Finds similar code components based on node2vec embeddings.

        Args:
            file_path: Path of the source code file.
            repo_id: Repository identifier.
            limit: Maximum number of similar components to return.

        Returns:
            List of dictionaries with similar code details.
        """
        try:
            return self.graph_analysis.find_similar_code(file_path, repo_id, limit=limit)
        except Exception as e:
            log(f"Error finding similar code for {file_path}: {e}", level="error")
            return []

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
        """
        Searches for code snippets matching the query using semantic search.
        """
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

    def analyze_documentation(self, repo_id: int) -> Dict:
        """Enhanced documentation analysis"""
        docs = get_repo_docs(repo_id)
        
        analysis = {
            "total_docs": len(docs),
            "doc_types": {},
            "clusters": self._analyze_doc_clusters(docs),
            "coverage": self._analyze_coverage(docs),
            "quality_metrics": self._batch_quality_analysis(docs),
            "version_history": self._analyze_versions(docs),
            "shared_docs": self._analyze_sharing(docs)
        }
        
        return analysis

    def _analyze_doc_clusters(self, docs: List[Dict]) -> Dict:
        """Cluster similar documentation together"""
        if not docs:
            return {}
            
        # Get embeddings for all docs
        embeddings = np.array([
            self.doc_embedder.embed(doc['content'])
            for doc in docs
        ])
        
        # Perform clustering
        clustering = DBSCAN(eps=0.3, min_samples=2).fit(embeddings)
        
        clusters = {}
        for i, label in enumerate(clustering.labels_):
            if label >= 0:  # Ignore noise points (-1)
                if label not in clusters:
                    clusters[label] = []
                clusters[label].append({
                    'id': docs[i]['id'],
                    'path': docs[i]['file_path'],
                    'similarity_score': self._calculate_cluster_coherence(
                        embeddings[i],
                        embeddings[clustering.labels_ == label]
                    )
                })
        
        return clusters

    def _analyze_coverage(self, docs: List[Dict]) -> Dict:
        """Analyze documentation coverage"""
        coverage = {
            "total_lines": sum(len(doc['content'].splitlines()) for doc in docs),
            "coverage_by_type": {},
            "missing_areas": [],
            "suggestions": []
        }
        
        # Analyze coverage by documentation type
        for doc in docs:
            doc_type = doc.get('doc_type', 'unknown')
            if doc_type not in coverage["coverage_by_type"]:
                coverage["coverage_by_type"][doc_type] = 0
            coverage["coverage_by_type"][doc_type] += 1
            
        # Identify potential gaps
        code_patterns = ['class', 'function', 'method', 'api']
        for pattern in code_patterns:
            if not any(pattern in doc['content'].lower() for doc in docs):
                coverage["missing_areas"].append(f"No documentation found for {pattern}")
                
        return coverage

    def _batch_quality_analysis(self, docs: List[Dict]) -> Dict:
        """Batch analyze documentation quality"""
        quality_metrics = {}
        
        for doc in docs:
            metrics = {
                "completeness": self._analyze_completeness(doc['content']),
                "clarity": self._analyze_clarity(doc['content']),
                "structure": self._analyze_structure(doc['content']),
                "maintainability": self._analyze_maintainability(doc),
                "consistency": self._analyze_consistency(doc, docs)
            }
            
            quality_metrics[doc['id']] = metrics
            
        return quality_metrics

    def _analyze_versions(self, docs: List[Dict]) -> Dict:
        """Analyze documentation version history"""
        version_analysis = {}
        
        for doc in docs:
            versions = self._get_doc_versions(doc['id'])
            if versions:
                version_analysis[doc['id']] = {
                    "version_count": len(versions),
                    "last_updated": versions[-1]['created_at'],
                    "change_summary": self._generate_change_summary(versions)
                }
                
        return version_analysis

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

    def close(self) -> None:
        """
        Clean up resources.
        """
        self.graph_analysis.close()