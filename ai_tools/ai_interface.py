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
        Performs comprehensive analysis, including code flow tracing.
        """
        try:
            return self.graph_analysis.trace_code_flow("entry_point", repo_id)
        except Exception as e:
            log(f"Error tracing code flow: {e}", level="error")
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

    def close(self) -> None:
        """
        Clean up resources.
        """
        self.graph_analysis.close()