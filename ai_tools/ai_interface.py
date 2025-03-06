"""[4.1] Unified AI Assistant Interface.

Flow:
1. Analysis Operations:
   - Repository analysis
   - Code structure analysis
   - Documentation analysis
   - Reference repository learning

2. Integration Points:
   - GraphAnalysis [4.3]: Graph operations
   - CodeUnderstanding [4.2]: Code analysis
   - SearchEngine [5.0]: Search operations
   - DocEmbedder [3.2]: Document embeddings
   - ReferenceRepositoryLearning [4.4]: Pattern learning

3. Error Handling:
   - ProcessingError: AI operations
   - AsyncErrorBoundary: Async operations
"""

from ai_tools.graph_capabilities import GraphAnalysis
from utils.logger import log
from ai_tools.code_understanding import CodeUnderstanding
from ai_tools.reference_repository_learning import reference_learning
from typing import List, Dict, Optional, Any, Set
from embedding.embedding_models import doc_embedder
from sklearn.cluster import DBSCAN
from difflib import SequenceMatcher
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    AsyncErrorBoundary,
    ErrorSeverity
)
from parsers.models import (
    FileType,
    FileClassification,
)
from parsers.types import (
    ParserResult,
    ExtractedFeatures,
)
import numpy as np
import os
import asyncio
from config import ParserConfig
from utils.shutdown import register_shutdown_handler


class AIAssistant:
    """[4.1.1] Unified AI assistance interface."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self.graph_analysis = None
        self.code_understanding = None
        self.doc_embedder = None
        self.reference_learning = None
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("AIAssistant not initialized. Use create() to initialize.")
        if not self.graph_analysis:
            raise ProcessingError("Graph analysis not initialized")
        if not self.code_understanding:
            raise ProcessingError("Code understanding not initialized")
        if not self.doc_embedder:
            raise ProcessingError("Document embedder not initialized")
        if not self.reference_learning:
            raise ProcessingError("Reference learning not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'AIAssistant':
        """Async factory method to create and initialize an AIAssistant instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="AI assistant initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize required components
                from ai_tools.graph_capabilities import GraphAnalysis
                from ai_tools.code_understanding import CodeUnderstanding
                from embedding.embedding_models import doc_embedder
                from ai_tools.reference_repository_learning import reference_learning
                
                # Initialize graph analysis
                instance.graph_analysis = await GraphAnalysis.create()
                
                # Initialize code understanding
                instance.code_understanding = await CodeUnderstanding.create()
                
                # Initialize embedders
                instance.doc_embedder = doc_embedder
                
                # Initialize reference learning
                instance.reference_learning = reference_learning
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                from utils.health_monitor import global_health_monitor
                global_health_monitor.register_component("ai_assistant")
                
                instance._initialized = True
                await log("AI Assistant initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing AI Assistant: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize AI Assistant: {e}")
    
    @handle_async_errors(error_types=ProcessingError)
    async def analyze_repository(self, repo_id: int) -> Dict[str, Any]:
        """Analyze repository using AI tools."""
        try:
            # Create tasks for parallel execution
            structure_task = asyncio.create_task(self.analyze_code_structure(repo_id))
            codebase_task = asyncio.create_task(self.code_understanding.analyze_codebase(repo_id))
            docs_task = asyncio.create_task(self.analyze_documentation(repo_id))
            
            self._pending_tasks.update({structure_task, codebase_task, docs_task})
            
            try:
                # Wait for all tasks to complete
                structure, codebase, docs = await asyncio.gather(
                    structure_task,
                    codebase_task,
                    docs_task
                )
            finally:
                self._pending_tasks.difference_update({structure_task, codebase_task, docs_task})
            
            return {
                "structure": structure,
                "codebase": codebase,
                "documentation": docs
            }
        except Exception as e:
            log(f"Error in repository analysis: {e}", level="error")
            return {}

    @handle_async_errors(error_types=ProcessingError)
    async def analyze_code_structure(
        self,
        repo_id: int,
        file_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Analyze code structure using graph capabilities."""
        async with AsyncErrorBoundary(
            operation_name="code structure analysis",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
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
        """Get comprehensive code context concurrently."""
        async with AsyncErrorBoundary(
            operation_name="code context retrieval",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            structure, references, context = await asyncio.gather(
                self.analyze_code_structure(repo_id, file_path),
                self.graph_analysis.get_references(repo_id, file_path),
                self.code_understanding.get_code_context(file_path, repo_id)
            )
            
            return {
                "structure": structure,
                "references": references,
                "context": context
            }

    @handle_errors(error_types=ProcessingError)
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
        except (ValueError, KeyError) as e:
            # Handle expected errors
            log(f"Error tracing code flow from {entry_point}: {e}", level="error")
            return []
        except Exception as e:
            # Handle unexpected errors
            import traceback
            log(f"Unexpected error tracing code flow from {entry_point}: {e}\n{traceback.format_exc()}", level="error")
            raise ProcessingError(f"Failed to trace code flow: {e}")

    @handle_async_errors(error_types=ProcessingError)
    async def search_code_snippets(self, query: str, repo_id: int, limit: int = 3) -> list:
        """Searches for code snippets matching the query using semantic search."""
        # Import locally to avoid circular dependencies
        from semantic.search import search_code
        try:
            return await search_code(query, repo_id, limit=limit)
        except ImportError as e:
            log(f"Search module not available: {e}", level="error")
            return []
        except ValueError as e:
            log(f"Invalid search parameters for query '{query}': {e}", level="error")
            return []
        except Exception as e:
            log(f"Unexpected error in semantic search for query '{query}': {e}", level="error")
            raise ProcessingError(f"Search operation failed: {e}")

    @handle_async_errors(error_types=ProcessingError)
    async def search_documentation(self, query: str, repo_id: int = None) -> list:
        """Search across all available documentation."""
        # Import locally to avoid circular dependencies
        from semantic.search import search_docs
        try:
            return await search_docs(query, repo_id, limit=3)
        except ImportError as e:
            log(f"Documentation search module not available: {e}", level="error")
            return []
        except ValueError as e:
            log(f"Invalid documentation search parameters for query '{query}': {e}", level="error")
            return []
        except Exception as e:
            log(f"Unexpected error searching documentation for query '{query}': {e}", level="error")
            raise ProcessingError(f"Documentation search operation failed: {e}")
    
    def get_available_docs(self, search_term: str, repo_id: int = None) -> list[dict]:
        """Find documentation that could be linked to a project."""
        # Import locally to avoid circular dependencies
        from semantic.search import search_available_docs
        return search_available_docs(search_term, repo_id)
    
    def share_documentation(self, doc_ids: list[int], target_repo_id: int) -> dict:
        """Share selected documentation with a target repository."""
        # Import locally to avoid circular dependencies
        from semantic.search import share_docs_with_repo
        return share_docs_with_repo(doc_ids, target_repo_id)

    @handle_async_errors(error_types=ProcessingError)
    async def analyze_documentation(self, repo_id: int) -> Dict[str, Any]:
        """[4.1.5] Analyze documentation quality, coverage, and clusters."""
        async with AsyncErrorBoundary(
            operation_name="documentation analysis",
            error_types=ProcessingError,
            severity=ErrorSeverity.ERROR
        ):
            try:
                # Import locally to avoid circular dependencies
                from semantic.search import get_repo_docs
                docs = await get_repo_docs(repo_id)
                if not docs:
                    return {"error": "No documentation found for this repository"}
                
                return {
                    "total_docs": len(docs),
                    "clusters": await self._analyze_doc_clusters(docs),
                    "coverage": await self._analyze_coverage(docs),
                    "quality": await self._batch_quality_analysis(docs)
                }
            except ImportError as e:
                log(f"Documentation module not available: {e}", level="error")
                return {"error": f"Documentation service unavailable: {e}"}
            except ValueError as e:
                log(f"Invalid repository ID ({repo_id}): {e}", level="error")
                return {"error": f"Invalid repository parameters: {e}"}
            except Exception as e:
                log(f"Unexpected error analyzing documentation: {e}", level="error")
                raise ProcessingError(f"Documentation analysis failed: {e}")

    @handle_errors(error_types=ProcessingError)
    async def _analyze_doc_clusters(self, docs: List[Dict]) -> Dict[str, Any]:
        """Cluster similar documentation."""
        async with AsyncErrorBoundary(
            operation_name="documentation clustering",
            error_types=ProcessingError,
            severity=ErrorSeverity.WARNING
        ):
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
                    clusters.setdefault(label, []).append({
                        'id': docs[i]['id'],
                        'path': docs[i]['file_path']
                    })
            
            return clusters

    @handle_errors(error_types=ProcessingError)
    async def _analyze_coverage(self, docs: List[Dict]) -> Dict[str, Any]:
        """Analyze documentation coverage."""
        async with AsyncErrorBoundary(
            operation_name="coverage analysis",
            error_types=ProcessingError,
            severity=ErrorSeverity.WARNING
        ):
            coverage = {
                "total_lines": sum(len(doc['content'].splitlines()) for doc in docs),
                "coverage_by_type": {},
                "missing_areas": []
            }
            
            for doc in docs:
                doc_type = doc.get('doc_type', 'unknown')
                coverage["coverage_by_type"][doc_type] = coverage["coverage_by_type"].get(doc_type, 0) + 1
            
            return coverage

    @handle_errors(error_types=ProcessingError)
    async def _batch_quality_analysis(self, docs: List[Dict]) -> Dict[str, Any]:
        """Analyze documentation quality by computing various metrics."""
        async with AsyncErrorBoundary(
            operation_name="quality analysis",
            error_types=ProcessingError,
            severity=ErrorSeverity.WARNING
        ):
            quality_metrics = {}
            
            for doc in docs:
                lines = doc['content'].splitlines()
                header_count = sum(1 for line in lines if line.strip().startswith("#"))
                structure_score = (header_count / len(lines)) if lines else 0

                metrics = {
                    "completeness": len(doc['content'].split()) / 100,  # Basic metric
                    "has_examples": 1.0 if "```" in doc['content'] else 0.0,
                    "has_sections": 1.0 if "#" in doc['content'] else 0.0,
                    "structure": structure_score  # Newly added structure metric
                }
                quality_metrics[doc['id']] = metrics
            
            return quality_metrics

    @handle_errors(error_types=ProcessingError)
    async def suggest_documentation_improvements(self, repo_id: int) -> List[Dict]:
        """Suggest improvements to documentation based on quality analysis."""
        try:
            # Import locally to avoid circular dependencies
            from semantic.search import get_repo_docs
            docs = await get_repo_docs(repo_id)
            if not docs:
                return [{"error": "No documentation found"}]
            
            suggestions = []
            for doc in docs:
                quality = await self._batch_quality_analysis([doc])[doc['id']]
                
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
        except KeyError as e:
            log(f"Error accessing document quality metrics: {e}", level="error")
            return [{"error": f"Missing document attribute: {e}"}]
        except ImportError as e:
            log(f"Error importing semantic search module: {e}", level="error")
            return [{"error": "Search module unavailable"}]
        except Exception as e:
            log(f"Unexpected error suggesting documentation improvements: {e}", level="error")
            raise ProcessingError(f"Failed to analyze documentation quality: {e}")

    @handle_errors(error_types=ProcessingError)
    async def track_doc_version(self, doc_id: int, new_content: str) -> Dict:
        """Track a new version of documentation."""
        changes = SequenceMatcher(None, "", new_content).ratio()
        # Import locally to avoid circular dependencies
        from semantic.search import update_doc_version
        return await update_doc_version(doc_id, new_content, changes)

    @handle_errors(error_types=ProcessingError)
    async def suggest_documentation_links(self, repo_id: int, threshold: float = 0.8) -> List[Dict]:
        """Suggest links between documentation and code."""
        # Import locally to avoid circular dependencies
        from semantic.search import get_repo_docs, search_docs
        repo_docs = await get_repo_docs(repo_id)
        all_docs = await search_docs("", limit=100)  # Get broader set of docs
        
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

    @handle_async_errors(error_types=ProcessingError)
    async def learn_from_reference_repo(self, reference_repo_id: int) -> Dict[str, Any]:
        """[4.1.11] Learn patterns from a reference repository."""
        async with AsyncErrorBoundary("reference repository learning"):
            return await self.reference_learning.learn_from_repository(reference_repo_id)
    
    @handle_async_errors(error_types=ProcessingError)
    async def apply_reference_patterns(
        self,
        reference_repo_id: int,
        target_repo_id: int
    ) -> Dict[str, Any]:
        """[4.1.12] Apply learned patterns from a reference repository to a target project."""
        async with AsyncErrorBoundary("applying reference patterns"):
            return await self.reference_learning.apply_patterns_to_project(
                reference_repo_id, target_repo_id
            )
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_repository_with_reference(
        self,
        repo_id: int,
        reference_repo_id: int
    ) -> Dict[str, Any]:
        """Analyze repository with reference to another one."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("repository analysis with reference"):
            # Create tasks for parallel execution
            analysis_task = asyncio.create_task(self.analyze_repository(repo_id))
            reference_task = asyncio.create_task(
                self.reference_learning.learn_from_repository(reference_repo_id)
            )
            comparison_task = asyncio.create_task(
                self.reference_learning.compare_with_reference_repository(
                    active_repo_id=repo_id,
                    reference_repo_id=reference_repo_id
                )
            )
            patterns_task = asyncio.create_task(
                self.reference_learning.apply_patterns_to_project(
                    reference_repo_id, repo_id
                )
            )
            
            self._pending_tasks.update({analysis_task, reference_task, comparison_task, patterns_task})
            
            try:
                # Wait for all tasks to complete
                analysis, reference_status, comparison, patterns = await asyncio.gather(
                    analysis_task,
                    reference_task,
                    comparison_task,
                    patterns_task
                )
            finally:
                self._pending_tasks.difference_update({analysis_task, reference_task, comparison_task, patterns_task})
            
            # Process results
            similar_files = []
            if comparison and "similar_files" in comparison:
                similar_files = comparison["similar_files"]
            
            return {
                "analysis": analysis,
                "reference_status": reference_status,
                "similar_files": similar_files,
                "patterns": patterns
            }

    @handle_async_errors(error_types=ProcessingError)
    async def search_patterns(
        self, 
        query_text: str, 
        repo_id: Optional[int] = None,
        pattern_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """[4.1.14] Search for code patterns matching the query."""
        async with AsyncErrorBoundary("pattern search"):
            from semantic.search import search_engine
            return await search_engine.search_patterns(
                query_text=query_text,
                repo_id=repo_id,
                pattern_type=pattern_type,
                limit=limit
            )
    
    @handle_async_errors(error_types=ProcessingError)
    async def get_repository_patterns(
        self,
        repo_id: int,
        pattern_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """[4.1.15] Get patterns extracted from a specific repository."""
        async with AsyncErrorBoundary("get repository patterns"):
            from semantic.search import search_engine
            return await search_engine.get_repository_patterns(
                repo_id=repo_id,
                pattern_type=pattern_type,
                limit=limit
            )
    
    @handle_async_errors(error_types=ProcessingError)
    async def deep_learn_from_multiple_repositories(
        self,
        repo_ids: List[int]
    ) -> Dict[str, Any]:
        """Deep learn from multiple reference repositories."""
        async with AsyncErrorBoundary("deep learning from multiple repositories"):
            # Create learning tasks for each repository
            learning_tasks = [
                asyncio.create_task(self.reference_learning.learn_from_repository(repo_id))
                for repo_id in repo_ids
            ]
            
            self._pending_tasks.update(learning_tasks)
            
            try:
                # Wait for all learning tasks to complete
                results = await asyncio.gather(*learning_tasks, return_exceptions=True)
            finally:
                self._pending_tasks.difference_update(learning_tasks)
            
            # Process results
            successful_repos = []
            failed_repos = []
            for repo_id, result in zip(repo_ids, results):
                if isinstance(result, Exception):
                    failed_repos.append({"repo_id": repo_id, "error": str(result)})
                else:
                    successful_repos.append({"repo_id": repo_id, "patterns": result})
            
            return {
                "successful_repositories": successful_repos,
                "failed_repositories": failed_repos,
                "total_patterns": sum(len(r["patterns"]) for r in successful_repos)
            }
    
    @handle_async_errors(error_types=ProcessingError)
    async def apply_cross_repository_patterns(
        self,
        target_repo_id: int,
        reference_repo_ids: List[int]
    ) -> Dict[str, Any]:
        """[4.1.17] Apply patterns learned from multiple reference repositories to a target project."""
        if not self._initialized:
            await self.ensure_initialized()
            
        async with AsyncErrorBoundary("applying cross-repository patterns"):
            return await self.reference_learning.apply_cross_repository_patterns(
                target_repo_id=target_repo_id,
                repo_ids=reference_repo_ids
            )
    
    @handle_errors(error_types=ProcessingError)
    async def cleanup(self) -> None:
        """Cleanup all resources."""
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
            
            # Cleanup components in reverse initialization order
            cleanup_tasks = []
            
            if self.reference_learning:
                task = asyncio.create_task(self.reference_learning.cleanup())
                cleanup_tasks.append(task)
            
            if self.doc_embedder:
                task = asyncio.create_task(self.doc_embedder.cleanup())
                cleanup_tasks.append(task)
            
            if self.code_understanding:
                task = asyncio.create_task(self.code_understanding.cleanup())
                cleanup_tasks.append(task)
            
            if self.graph_analysis:
                task = asyncio.create_task(self.graph_analysis.cleanup())
                cleanup_tasks.append(task)
            
            # Wait for all cleanup tasks
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            # Unregister from health monitoring
            from utils.health_monitor import global_health_monitor
            global_health_monitor.unregister_component("ai_assistant")
            
            self._initialized = False
            await log("All AI resources cleaned up.", level="info")
        except Exception as e:
            await log(f"Error cleaning up AI resources: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup AI resources: {e}")

    # Optional alias to match documentation
    async def find_similar_code(self, query: str, repo_id: Optional[int] = None, limit: int = 5) -> list:
        """Find similar code based on semantic search."""
        # Import locally to avoid circular dependencies
        from semantic.search import semantic_search
        return await semantic_search(query, "code", repo_id, limit)

# Do not create global instance until implementation is ready
ai_assistant = None