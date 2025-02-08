"""
Unified AI Assistant Interface

This module exposes a simple facade combining core capabilities:
– Graph analysis for code structure, metrics, tracing,
– Semantic code search.
Future enhancements (caching, additional AI models, etc.) can be easily plugged in here.
"""

from ai_tools.graph_capabilities import GraphAnalysisCapabilities
from semantic.semantic_search import search_code
from utils.logger import log


class AIAssistantInterface:
    """
    A unified interface for the AI assistant functionalities.

    This class wraps the graph analysis capabilities and semantic search,
    exposing a simplified API for code analysis tasks.
    """
    def __init__(self):
        self.graph_analysis = GraphAnalysisCapabilities()
        # Additional AI tools can be initialized here in the future.

    def analyze_repository(self, repo_id: int) -> dict:
        """
        Performs comprehensive analysis of a repository.
        Combines code structure analysis with code metrics.

        Args:
            repo_id: Repository identifier.

        Returns:
            A combined dictionary with structure and metrics.
        """
        try:
            structure = self.graph_analysis.analyze_code_structure(repo_id)
            metrics = self.graph_analysis.get_code_metrics(repo_id)
            return {
                "structure": structure,
                "metrics": metrics
            }
        except Exception as e:
            log(f"Error analyzing repository {repo_id}: {e}", level="error")
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
        Searches for code snippets matching the provided query using semantic search.
        
        Args:
            query: The search term.
            repo_id: Repository identifier.
            limit: Maximum number of results.

        Returns:
            List of code snippet search results.
        """
        try:
            return search_code(query, repo_id=repo_id, limit=limit)
        except Exception as e:
            log(f"Error in semantic search for query '{query}': {e}", level="error")
            return []

    def close(self) -> None:
        """
        Clean up resources.
        """
        self.graph_analysis.close()