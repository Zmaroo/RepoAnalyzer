"""[4.4] Reference Repository Learning

Flow:
1. Learning Operations:
   - Extract patterns from reference repositories
   - Identify best practices and conventions
   - Create learning vectors for patterns
   - Identify similarities between current project and reference repos
   - Support both custom and tree-sitter parsers

2. Integration Points:
   - CodeEmbedder [3.1]: Code embeddings
   - Neo4jProjections [6.2]: Graph operations
   - AIAssistant [4.1]: AI interface
   - CodeUnderstanding [4.2]: Code analysis
   - Tree-sitter Language Pack: AST analysis
   - Custom Parsers: Specialized parsing

3. Error Handling:
   - ProcessingError: Learning operations
   - DatabaseError: Storage operations
"""

from typing import Dict, List, Optional, Any, Tuple, Set
import asyncio
import numpy as np
from utils.logger import log
from db.connection import connection_manager
from db.transaction import transaction_scope
from db.upsert_ops import coordinator as upsert_coordinator
from db.graph_sync import graph_sync
from db.neo4j_ops import Neo4jTools, run_query, get_neo4j_tools
from db.psql import query, execute
from db.retry_utils import (
    with_retry,
    RetryableError,
    NonRetryableError,
    RetryManager,
    RetryConfig
)
from embedding.embedding_models import code_embedder, doc_embedder
from utils.error_handling import (
    handle_errors,
    handle_async_errors,
    ProcessingError,
    DatabaseError,
    AsyncErrorBoundary,
    TransactionError,
    ErrorSeverity,
    Neo4jError
)
from parsers.models import (
    FileType,
    FileClassification,
)
from parsers.types import (
    Documentation,
    ComplexityMetrics,
    ExtractedFeatures,
    ParserResult,
    ParserType
)
from tree_sitter_language_pack import get_binding, get_language, get_parser, SupportedLanguage
from ai_tools.code_understanding import CodeUnderstanding
import os
from utils.async_runner import submit_async_task
from utils.shutdown import register_shutdown_handler
from utils.health_monitor import global_health_monitor, ComponentStatus


class ReferenceRepositoryLearning:
    """[4.4.1] Reference repository learning capabilities."""
    
    def __init__(self):
        """Private constructor - use create() instead."""
        self._initialized = False
        self.code_understanding = None
        self.embedder = None
        self.doc_embedder = None
        self.neo4j_tools = None
        self._retry_manager = None
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._tree_sitter_parsers = {}  # Cache for tree-sitter parsers
        self._parser_metrics = {
            ParserType.CUSTOM: {"patterns": 0, "success": 0},
            ParserType.TREE_SITTER: {"patterns": 0, "success": 0}
        }
    
    async def ensure_initialized(self):
        """Ensure the instance is properly initialized before use."""
        if not self._initialized:
            raise ProcessingError("ReferenceRepositoryLearning not initialized. Use create() to initialize.")
        if not self.code_understanding:
            raise ProcessingError("Code understanding not initialized")
        if not self.neo4j_tools:
            raise ProcessingError("Neo4j tools not initialized")
        return True
    
    @classmethod
    async def create(cls) -> 'ReferenceRepositoryLearning':
        """Async factory method to create and initialize a ReferenceRepositoryLearning instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary(
                operation_name="reference repository learning initialization",
                error_types=ProcessingError,
                severity=ErrorSeverity.CRITICAL
            ):
                # Initialize components
                instance.code_understanding = await CodeUnderstanding.create()
                instance.embedder = code_embedder
                instance.doc_embedder = doc_embedder
                instance.neo4j_tools = await get_neo4j_tools()
                
                # Initialize retry manager
                instance._retry_manager = RetryManager(
                    RetryConfig(max_retries=5, base_delay=1.0, max_delay=30.0)
                )
                
                # Initialize tree-sitter parsers
                await instance._initialize_tree_sitter_parsers()
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                # Initialize health monitoring
                global_health_monitor.register_component(
                    "reference_repository_learning",
                    health_check=instance._check_health
                )
                
                instance._initialized = True
                await log("Reference repository learning initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing reference repository learning: {e}", level="error")
            # Cleanup on initialization failure
            await instance.cleanup()
            raise ProcessingError(f"Failed to initialize reference repository learning: {e}")
    
    async def _check_health(self) -> Dict[str, Any]:
        """Health check for reference repository learning."""
        return {
            "status": ComponentStatus.HEALTHY if self._initialized else ComponentStatus.UNHEALTHY,
            "metrics": {
                "custom_patterns": self._parser_metrics[ParserType.CUSTOM]["patterns"],
                "tree_sitter_patterns": self._parser_metrics[ParserType.TREE_SITTER]["patterns"],
                "custom_success_rate": self._parser_metrics[ParserType.CUSTOM]["success"] / max(1, self._parser_metrics[ParserType.CUSTOM]["patterns"]),
                "tree_sitter_success_rate": self._parser_metrics[ParserType.TREE_SITTER]["success"] / max(1, self._parser_metrics[ParserType.TREE_SITTER]["patterns"])
            },
            "components": {
                "code_understanding": self.code_understanding is not None,
                "neo4j_tools": self.neo4j_tools is not None,
                "embedder": self.embedder is not None,
                "doc_embedder": self.doc_embedder is not None,
                "retry_manager": self._retry_manager is not None
            }
        }
    
    async def cleanup(self):
        """Clean up all resources."""
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
            
            # Clean up components in reverse initialization order
            if self.code_understanding:
                await self.code_understanding.cleanup()
            
            if self.neo4j_tools:
                await self.neo4j_tools.cleanup()
            
            if self._retry_manager:
                await self._retry_manager.cleanup()
            
            # Clean up tree-sitter parsers
            self._tree_sitter_parsers.clear()
            
            # Unregister from health monitoring
            global_health_monitor.unregister_component("reference_repository_learning")
            
            self._initialized = False
            await log("Reference repository learning cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up reference repository learning: {e}", level="error")
            raise ProcessingError(f"Failed to cleanup reference repository learning: {e}")
    
    async def _initialize_tree_sitter_parsers(self):
        """Initialize tree-sitter parsers for supported languages."""
        try:
            for lang in SupportedLanguage.__args__:
                try:
                    parser = get_parser(lang)
                    if parser:
                        self._tree_sitter_parsers[lang] = parser
                except Exception as e:
                    await log(f"Error initializing tree-sitter parser for {lang}: {e}", level="warning")
        except Exception as e:
            await log(f"Error initializing tree-sitter parsers: {e}", level="error")
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def learn_from_repository(self, reference_repo_id: int) -> Dict[str, Any]:
        """[4.4.2] Learn patterns and best practices from a reference repository."""
        async with AsyncErrorBoundary("reference repository learning"):
            # Extract code patterns
            code_patterns = await self._extract_code_patterns(reference_repo_id)
            
            # Extract documentation patterns
            doc_patterns = await self._extract_doc_patterns(reference_repo_id)
            
            # Extract architecture patterns
            arch_patterns = await self._extract_architecture_patterns(reference_repo_id)
            
            # Store patterns using transaction coordination
            async with transaction_scope() as txn:
                await txn.track_repo_change(reference_repo_id)
                
                # Store patterns in database
                pattern_ids = await self._store_patterns(reference_repo_id, code_patterns, doc_patterns, arch_patterns)
                
                # Create pattern graph projection
                await graph_sync.ensure_pattern_projection(reference_repo_id)
                
                # Run pattern similarity analysis
                similarity_results = await self.neo4j_tools.find_similar_patterns(reference_repo_id, limit=10)
                
                # Find pattern clusters using graph projections
                pattern_clusters = await graph_sync.compare_repository_structures(reference_repo_id, reference_repo_id)
                
                # Update parser metrics
                for pattern in code_patterns:
                    parser_type = pattern.get("parser_type", ParserType.UNKNOWN)
                    if parser_type in self._parser_metrics:
                        self._parser_metrics[parser_type]["patterns"] += 1
                        if pattern.get("success", False):
                            self._parser_metrics[parser_type]["success"] += 1
                
                return {
                    "code_patterns": len(code_patterns),
                    "doc_patterns": len(doc_patterns),
                    "architecture_patterns": len(arch_patterns),
                    "pattern_similarities": len(similarity_results),
                    "pattern_clusters": len(pattern_clusters.get("similarities", [])),
                    "repository_id": reference_repo_id,
                    "parser_metrics": self._parser_metrics
                }
    
    @handle_async_errors(error_types=ProcessingError)
    async def _extract_code_patterns(self, repo_id: int) -> List[Dict[str, Any]]:
        """Extract code patterns from repository."""
        patterns = []
        
        # Get all code files using transaction scope
        async with transaction_scope() as txn:
            files_query = """
                SELECT file_path, file_content, language, parser_type 
                FROM code_snippets 
                WHERE repo_id = $1 AND file_content IS NOT NULL
            """
            files = await query(files_query, (repo_id,))
            
            # Process files to extract patterns
            for file in files:
                parser_type = ParserType(file["parser_type"])
                
                # Get code structure from Neo4j
                structure_query = """
                    MATCH (f:Code {repo_id: $repo_id, file_path: $file_path})-[:CONTAINS]->(n)
                    RETURN n.type as node_type, n.name as name, COUNT(n) as count
                    ORDER BY count DESC
                    LIMIT 20
                """
                structure = await run_query(structure_query, {
                    "repo_id": repo_id,
                    "file_path": file["file_path"]
                })
                
                # Extract common patterns based on structure
                if structure:
                    common_nodes = [node for node in structure if node["count"] > 3]
                    if common_nodes:
                        # Create embedding for this pattern
                        pattern_text = file["file_content"][:1000]  # First 1000 chars as sample
                        
                        # Default value in case of error
                        embedding_list = None
                        ast = None
                        
                        # Create embedding with specific error handling
                        async def create_embedding():
                            nonlocal embedding_list
                            embedding = self.embedder.embed(pattern_text)
                            embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else None
                        
                        # Get AST if using tree-sitter
                        if parser_type == ParserType.TREE_SITTER and file["language"] in self._tree_sitter_parsers:
                            try:
                                parser = self._tree_sitter_parsers[file["language"]]
                                tree = parser.parse(bytes(pattern_text, "utf8"))
                                if tree:
                                    ast = self._convert_tree_to_dict(tree.root_node)
                            except Exception as e:
                                await log(f"Error getting tree-sitter AST: {e}", level="warning")
                        
                        # Use AsyncErrorBoundary with specific error types
                        try:
                            async with AsyncErrorBoundary("pattern embedding", 
                                            error_types=(ValueError, ImportError, ProcessingError),
                                            severity=ErrorSeverity.WARNING):
                                await create_embedding()
                        except Exception as e:
                            log(f"Error creating embedding: {e}", level="error")
                            
                        pattern = {
                            "file_path": file["file_path"],
                            "language": file["language"],
                            "pattern_type": "code_structure",
                            "elements": common_nodes,
                            "sample": pattern_text,
                            "embedding": embedding_list,
                            "parser_type": parser_type,
                            "ast": ast,
                            "success": embedding_list is not None or ast is not None
                        }
                        patterns.append(pattern)
        
        return patterns
    
    def _convert_tree_to_dict(self, node) -> Dict[str, Any]:
        """Convert a tree-sitter node to a dictionary."""
        result = {
            "type": node.type,
            "start_point": node.start_point,
            "end_point": node.end_point
        }
        
        if len(node.children) > 0:
            result["children"] = [self._convert_tree_to_dict(child) for child in node.children]
        
        return result
    
    @handle_async_errors(error_types=ProcessingError)
    async def _extract_doc_patterns(self, repo_id: int) -> List[Dict[str, Any]]:
        """Extract documentation patterns from repository."""
        patterns = []
        
        # Get all documentation using transaction scope
        async with transaction_scope() as txn:
            docs_query = """
                SELECT d.doc_id, d.title, d.content, d.doc_type, f.file_path, f.parser_type
                FROM repo_docs d
                JOIN repo_doc_relations r ON d.id = r.doc_id
                JOIN code_files f ON f.file_path = d.file_path AND f.repo_id = r.repo_id
                WHERE r.repo_id = $1
            """
            docs = await query(docs_query, (repo_id,))
            
            # Analyze documentation structure and patterns
            doc_types = {}
            for doc in docs:
                doc_type = doc["doc_type"]
                if doc_type not in doc_types:
                    doc_types[doc_type] = []
                doc_types[doc_type].append(doc)
            
            # Extract patterns for each documentation type
            for doc_type, type_docs in doc_types.items():
                if len(type_docs) > 3:  # Only consider if we have enough examples
                    # Create combined embedding for these doc samples
                    sample_texts = [doc["content"][:500] for doc in type_docs[:3]]
                    combined_text = "\n".join(sample_texts)
                    
                    try:
                        embedding = self.doc_embedder.embed(combined_text)
                        embedding_list = embedding.tolist() if isinstance(embedding, np.ndarray) else None
                    except Exception as e:
                        await log(f"Error creating doc embedding: {e}", level="error")
                        embedding_list = None
                    
                    pattern = {
                        "doc_type": doc_type,
                        "pattern_type": "documentation",
                        "count": len(type_docs),
                        "samples": sample_texts,
                        "common_structure": self._analyze_doc_structure(type_docs),
                        "embedding": embedding_list,
                        "parser_type": ParserType(type_docs[0]["parser_type"]),
                        "success": embedding_list is not None
                    }
                    patterns.append(pattern)
        
        return patterns
    
    @handle_errors(error_types=ProcessingError)
    def _analyze_doc_structure(self, docs: List[Dict]) -> Dict[str, Any]:
        """Analyze the common structure of documentation."""
        # Analyze headings
        headings = []
        for doc in docs:
            content = doc["content"]
            doc_headings = []
            for line in content.split('\n'):
                line = line.strip()
                # Simple markdown heading detection
                if line.startswith('#'):
                    level = 0
                    while level < len(line) and line[level] == '#':
                        level += 1
                    if level < len(line) and line[level] == ' ':
                        heading = line[level+1:].strip()
                        doc_headings.append({"level": level, "text": heading})
            
            if doc_headings:
                headings.append(doc_headings)
        
        # Find common patterns in headings
        common_headings = []
        if headings:
            # Extract most common first-level heading
            all_first_level = []
            for doc_headings in headings:
                first_level = [h for h in doc_headings if h["level"] == 1]
                if first_level:
                    all_first_level.extend(first_level)
            
            # Count occurrences
            heading_counts = {}
            for heading in all_first_level:
                text = heading["text"].lower()
                if text not in heading_counts:
                    heading_counts[text] = 0
                heading_counts[text] += 1
            
            # Get most common headings
            common_headings = sorted(
                [{"text": text, "count": count} for text, count in heading_counts.items()],
                key=lambda x: x["count"],
                reverse=True
            )[:5]  # Top 5 most common
            
        return {
            "common_headings": common_headings,
            "avg_heading_count": sum(len(h) for h in headings) / max(1, len(headings))
        }
    
    @handle_async_errors(error_types=ProcessingError)
    async def _extract_architecture_patterns(self, repo_id: int) -> List[Dict[str, Any]]:
        """Extract architecture patterns from repository."""
        patterns = []
        
        # Get repository structure with parser types
        structure_query = """
            SELECT file_path, parser_type 
            FROM file_metadata 
            WHERE repo_id = $repo_id
            ORDER BY file_path
        """
        files = await query(structure_query, {"repo_id": repo_id})
        
        # Extract directory structure
        directories = {}
        parser_types = {}
        for file in files:
            path = file["file_path"]
            parts = path.split('/')
            current = directories
            for i, part in enumerate(parts[:-1]):  # Skip filename
                if part not in current:
                    current[part] = {}
                    parser_types[part] = ParserType(file["parser_type"])
                current = current[part]
        
        # Identify common architectural patterns
        if directories:
            pattern = {
                "pattern_type": "architecture",
                "directory_structure": directories,
                "top_level_dirs": list(directories.keys()),
                "parser_distribution": {
                    dir_name: parser_type.value
                    for dir_name, parser_type in parser_types.items()
                }
            }
            patterns.append(pattern)
            
            # Get dependencies between components
            graph_name = f"code-repo-{repo_id}"
            try:
                dependencies = await self.neo4j_tools.get_component_dependencies(graph_name)
                if dependencies:
                    pattern = {
                        "pattern_type": "component_dependencies",
                        "dependencies": dependencies,
                        "parser_distribution": {
                            dep["source"]: parser_types.get(dep["source"].split('/')[0], ParserType.UNKNOWN).value
                            for dep in dependencies
                        }
                    }
                    patterns.append(pattern)
            except Exception as e:
                log(f"Error getting component dependencies: {e}", level="error")
        
        return patterns
    
    @handle_async_errors(error_types=DatabaseError)
    async def _store_patterns(
        self, 
        repo_id: int, 
        code_patterns: List[Dict], 
        doc_patterns: List[Dict], 
        arch_patterns: List[Dict]
    ) -> List[int]:
        """Store extracted patterns in database and Neo4j."""
        pattern_ids = []
        
        async with transaction_scope() as txn:
            # Store code patterns
            for pattern in code_patterns:
                # Store in PostgreSQL using upsert coordinator
                pattern_data = {
                    "repo_id": repo_id,
                    "file_path": pattern["file_path"],
                    "language": pattern["language"],
                    "pattern_type": pattern["pattern_type"],
                    "elements": pattern["elements"],
                    "sample": pattern["sample"],
                    "embedding": pattern["embedding"]
                }
                
                # Use upsert coordinator to store pattern
                pattern_id = await upsert_coordinator.store_parsed_content(
                    repo_id=repo_id,
                    file_path=pattern["file_path"],
                    ast={"elements": pattern["elements"]},
                    features=ExtractedFeatures(pattern_data)
                )
                
                if pattern_id:
                    pattern_ids.append(pattern_id)
                    
                    # Store pattern node in Neo4j
                    await self.neo4j_tools.store_pattern_node({
                        "repo_id": repo_id,
                        "pattern_id": pattern_id,
                        "pattern_type": pattern["pattern_type"],
                        "language": pattern["language"],
                        "file_path": pattern["file_path"],
                        "embedding": pattern["embedding"],
                        "elements": pattern["elements"]
                    })
            
            # Store documentation patterns
            for pattern in doc_patterns:
                # Store in PostgreSQL using upsert coordinator
                doc_id = await upsert_coordinator.upsert_doc(
                    repo_id=repo_id,
                    file_path=f"patterns/{pattern['doc_type']}/pattern_{len(pattern_ids)}.md",
                    content="\n".join(pattern["samples"]),
                    doc_type=pattern["doc_type"],
                    metadata={
                        "pattern_type": pattern["pattern_type"],
                        "count": pattern["count"],
                        "common_structure": pattern["common_structure"]
                    }
                )
                
                if doc_id:
                    pattern_ids.append(doc_id)
            
            # Store architecture patterns
            for pattern in arch_patterns:
                if pattern["pattern_type"] == "architecture":
                    # Store in PostgreSQL
                    arch_data = {
                        "repo_id": repo_id,
                        "pattern_type": pattern["pattern_type"],
                        "directory_structure": pattern["directory_structure"],
                        "top_level_dirs": pattern["top_level_dirs"]
                    }
                    
                    # Use upsert coordinator
                    pattern_id = await upsert_coordinator.store_parsed_content(
                        repo_id=repo_id,
                        file_path="architecture/structure.json",
                        ast=arch_data,
                        features=ExtractedFeatures(arch_data)
                    )
                    
                    if pattern_id:
                        pattern_ids.append(pattern_id)
                
                elif pattern["pattern_type"] == "component_dependencies":
                    # Store in PostgreSQL
                    dep_data = {
                        "repo_id": repo_id,
                        "pattern_type": pattern["pattern_type"],
                        "dependencies": pattern["dependencies"]
                    }
                    
                    # Use upsert coordinator
                    pattern_id = await upsert_coordinator.store_parsed_content(
                        repo_id=repo_id,
                        file_path="architecture/dependencies.json",
                        ast=dep_data,
                        features=ExtractedFeatures(dep_data)
                    )
                    
                    if pattern_id:
                        pattern_ids.append(pattern_id)
            
            # Link patterns to repository
            await self.neo4j_tools.link_patterns_to_repository(repo_id, pattern_ids, is_reference=True)
        
        return pattern_ids
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def apply_patterns_to_project(
        self, 
        reference_repo_id: int, 
        target_repo_id: int
    ) -> Dict[str, Any]:
        """[4.4.3] Apply learned patterns to a target project."""
        async with AsyncErrorBoundary("applying reference patterns"):
            async with transaction_scope() as txn:
                await txn.track_repo_change(target_repo_id)
                
                # Get patterns from reference repository
                code_patterns = await self._get_code_patterns(reference_repo_id)
                doc_patterns = await self._get_doc_patterns(reference_repo_id)
                arch_patterns = await self._get_arch_patterns(reference_repo_id)
                
                # Analyze target repository
                target_analysis = await self.code_understanding.analyze_codebase(target_repo_id)
                
                # Use graph sync for repository comparison
                comparison_results = await graph_sync.compare_repository_structures(
                    active_repo_id=target_repo_id,
                    reference_repo_id=reference_repo_id
                )
                
                # Log comparison results
                log(f"Repository structure comparison complete with {comparison_results.get('similarity_count', 0)} similarities found", 
                    level="info")
                
                # Generate recommendations using comparison results
                code_recommendations = await self._generate_enhanced_code_recommendations(
                    code_patterns, target_repo_id, target_analysis, comparison_results
                )
                
                doc_recommendations = self._generate_doc_recommendations(
                    doc_patterns, target_repo_id
                )
                
                arch_recommendations = self._generate_arch_recommendations(
                    arch_patterns, target_repo_id, target_analysis
                )
                
                # Link applied patterns to target repository in Neo4j
                pattern_ids = [
                    rec["pattern_id"] for rec in code_recommendations + doc_recommendations + arch_recommendations
                    if "pattern_id" in rec
                ]
                if pattern_ids:
                    await self.neo4j_tools.link_patterns_to_repository(
                        target_repo_id, pattern_ids, is_reference=False
                    )
                
                return {
                    "code_recommendations": code_recommendations,
                    "doc_recommendations": doc_recommendations,
                    "arch_recommendations": arch_recommendations,
                    "reference_repo_id": reference_repo_id,
                    "target_repo_id": target_repo_id,
                    "applied_patterns": len(pattern_ids),
                    "similarity_score": comparison_results.get("similarity_count", 0) / 20 if comparison_results.get("similarity_count") else 0
                }
    
    @handle_async_errors(error_types=DatabaseError)
    async def _get_code_patterns(self, repo_id: int) -> List[Dict]:
        """Get code patterns from database."""
        async with transaction_scope() as txn:
            patterns_query = """
                SELECT p.*, c.file_path, c.language
                FROM code_patterns p
                JOIN code_snippets c ON c.id = p.code_id
                WHERE c.repo_id = $1
            """
            return await query(patterns_query, (repo_id,))
    
    @handle_async_errors(error_types=DatabaseError)
    async def _get_doc_patterns(self, repo_id: int) -> List[Dict]:
        """Get documentation patterns from database."""
        async with transaction_scope() as txn:
            patterns_query = """
                SELECT d.*, r.repo_id
                FROM repo_docs d
                JOIN repo_doc_relations r ON d.id = r.doc_id
                WHERE r.repo_id = $1 AND d.doc_type = 'pattern'
            """
            return await query(patterns_query, (repo_id,))
    
    @handle_async_errors(error_types=DatabaseError)
    async def _get_arch_patterns(self, repo_id: int) -> List[Dict]:
        """Get architecture patterns from database."""
        async with transaction_scope() as txn:
            patterns_query = """
                SELECT c.*
                FROM code_snippets c
                WHERE c.repo_id = $1 
                AND c.file_path LIKE 'architecture/%'
            """
            return await query(patterns_query, (repo_id,))
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def _generate_enhanced_code_recommendations(
        self, 
        patterns: List[Dict], 
        target_repo_id: int, 
        target_analysis: Dict,
        comparison_results: Dict[str, Any]
    ) -> List[Dict]:
        """Generate code recommendations based on patterns using graph comparison results."""
        recommendations = []
        
        # Use similarity results from graph comparison for targeted recommendations
        if "similarities" in comparison_results and comparison_results["similarities"]:
            for similarity in comparison_results["similarities"]:
                active_file = similarity.get("active_file")
                reference_file = similarity.get("reference_file")
                similarity_score = similarity.get("similarity")
                
                # Find patterns related to the reference file
                matching_patterns = []
                for pattern in patterns:
                    if pattern.get("file_path") == reference_file:
                        matching_patterns.append(pattern)
                
                # Generate recommendations based on these patterns
                for pattern in matching_patterns:
                    recommendation = {
                        "pattern_type": pattern["pattern_type"],
                        "language": pattern["language"],
                        "target_file": active_file,
                        "reference_file": reference_file,
                        "recommendation": f"Apply {pattern['pattern_type']} pattern from {reference_file} to {active_file}",
                        "similarity": similarity_score,
                        "confidence": 0.85,  # Higher confidence with graph-based similarity
                        "sample": pattern.get("sample"),
                        "pattern_id": pattern.get("id")
                    }
                    recommendations.append(recommendation)
        
        # If no recommendations from graph comparison, fall back to Neo4j similarity
        if not recommendations:
            # Get target repository files
            async with transaction_scope() as txn:
                files_query = """
                    SELECT file_path, language 
                    FROM code_snippets 
                    WHERE repo_id = $1
                """
                files = await query(files_query, (target_repo_id,))
                
                # For each file, find matching patterns using Neo4j
                for file in files:
                    # Get recommendations for this file
                    pattern_recs = await self.neo4j_tools.find_similar_patterns(
                        target_repo_id, file["file_path"], limit=3
                    )
                    
                    for pattern in pattern_recs:
                        # Check if pattern is from one of our reference patterns
                        if any(p["id"] == pattern["pattern_id"] for p in patterns):
                            recommendation = {
                                "pattern_type": pattern["pattern_type"],
                                "language": pattern["language"],
                                "target_file": file["file_path"],
                                "recommendation": f"Consider using this {pattern['language']} pattern",
                                "sample": pattern.get("sample"),
                                "confidence": 0.75,  # Default confidence
                                "pattern_id": pattern["pattern_id"]
                            }
                            recommendations.append(recommendation)
        
        # If still no recommendations, fall back to language matching
        if not recommendations:
            async with transaction_scope() as txn:
                languages_query = """
                    SELECT DISTINCT language 
                    FROM code_snippets 
                    WHERE repo_id = $1 AND language IS NOT NULL
                """
                languages = await query(languages_query, (target_repo_id,))
                target_languages = [lang["language"] for lang in languages]
                
                # Filter patterns by target languages
                filtered_patterns = [
                    p for p in patterns if p["language"] in target_languages
                ]
                
                # Generate recommendations
                for pattern in filtered_patterns[:5]:  # Limit to 5 general recommendations
                    recommendation = {
                        "pattern_type": pattern["pattern_type"],
                        "language": pattern["language"],
                        "recommendation": f"Consider using this {pattern['language']} pattern",
                        "sample": pattern.get("sample"),
                        "confidence": 0.7,  # Lower confidence for language-only matching
                        "pattern_id": pattern.get("id")
                    }
                    recommendations.append(recommendation)
        
        return recommendations
    
    @handle_errors(error_types=ProcessingError)
    def _generate_doc_recommendations(self, patterns: List[Dict], target_repo_id: int) -> List[Dict]:
        """Generate documentation recommendations based on patterns."""
        recommendations = []
        
        try:
            # Generate recommendations for each pattern
            for pattern in patterns:
                recommendation = {
                    "doc_type": pattern["doc_type"],
                    "pattern_type": pattern["pattern_type"],
                    "recommendation": f"Consider using this documentation pattern for {pattern['doc_type']}",
                    "structure": pattern["common_structure"],
                    "confidence": 0.8,  # Default confidence
                    "pattern_id": pattern["pattern_id"]
                }
                recommendations.append(recommendation)
        except Exception as e:
            log(f"Error generating doc recommendations: {e}", level="error")
        
        return recommendations
    
    @handle_errors(error_types=ProcessingError)
    def _generate_arch_recommendations(
        self, 
        patterns: List[Dict], 
        target_repo_id: int, 
        target_analysis: Dict
    ) -> List[Dict]:
        """Generate architecture recommendations based on patterns."""
        recommendations = []
        
        try:
            # Generate recommendations for each pattern
            for pattern in patterns:
                if pattern["pattern_type"] == "architecture":
                    recommendation = {
                        "pattern_type": pattern["pattern_type"],
                        "recommendation": "Consider this directory structure",
                        "top_level_dirs": pattern["top_level_dirs"],
                        "confidence": 0.8,  # Default confidence
                        "pattern_id": pattern["pattern_id"]
                    }
                    recommendations.append(recommendation)
                elif pattern["pattern_type"] == "component_dependencies":
                    recommendation = {
                        "pattern_type": pattern["pattern_type"],
                        "recommendation": "Consider these component relationships",
                        "dependencies": pattern["dependencies"],
                        "confidence": 0.7,  # Default confidence
                        "pattern_id": pattern["pattern_id"]
                    }
                    recommendations.append(recommendation)
        except Exception as e:
            log(f"Error generating arch recommendations: {e}", level="error")
        
        return recommendations
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_pattern_relationships(self, repo_id: int) -> Dict[str, Any]:
        """[4.4.4] Analyze relationships between patterns using graph algorithms."""
        from utils.async_runner import submit_async_task
        
        tasks = set()
        try:
            # Use the enhanced graph_sync for pattern projection management
            future = submit_async_task(graph_sync.ensure_pattern_projection(repo_id))
            tasks.add(future)
            try:
                await asyncio.wrap_future(future)
            finally:
                tasks.remove(future)
            
            pattern_graph_name = f"pattern-repo-{repo_id}"
            
            # Run pattern similarity analysis
            future = submit_async_task(self.neo4j_tools.find_similar_patterns(repo_id, limit=10))
            tasks.add(future)
            try:
                similarity_results = await asyncio.wrap_future(future)
            finally:
                tasks.remove(future)
            
            # Find pattern clusters
            future = submit_async_task(graph_sync.compare_repository_structures(repo_id, repo_id))
            tasks.add(future)
            try:
                pattern_clusters = await asyncio.wrap_future(future)
            finally:
                tasks.remove(future)
            
            return {
                "pattern_similarities": len(similarity_results),
                "pattern_clusters": len(pattern_clusters.get("similarities", [])),
                "total_similarities": len(similarity_results),
                "total_clusters": len(pattern_clusters.get("similarities", []))
            }
        finally:
            # Clean up any remaining tasks
            if tasks:
                await asyncio.gather(*[asyncio.wrap_future(f) for f in tasks], return_exceptions=True)
                tasks.clear()
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def compare_with_reference_repository(
        self, 
        active_repo_id: int, 
        reference_repo_id: int
    ) -> Dict[str, Any]:
        """[4.4.5] Compare active repository with reference repository using graph projections."""
        # Ensure both repositories have projections
        await graph_sync.ensure_projection(active_repo_id)
        await graph_sync.ensure_projection(reference_repo_id)
        
        # Use the new comparison method from graph_sync
        comparison_results = await graph_sync.compare_repository_structures(
            active_repo_id=active_repo_id,
            reference_repo_id=reference_repo_id
        )
        
        # Enhance with additional pattern analysis
        patterns_query = """
            SELECT COUNT(*) as pattern_count 
            FROM (
                SELECT pattern_id FROM code_patterns WHERE repo_id = $repo_id
                UNION
                SELECT pattern_id FROM doc_patterns WHERE repo_id = $repo_id
                UNION
                SELECT pattern_id FROM arch_patterns WHERE repo_id = $repo_id
            ) AS patterns
        """
        active_patterns = await query(patterns_query, {"repo_id": active_repo_id})
        reference_patterns = await query(patterns_query, {"repo_id": reference_repo_id})
        
        # Add pattern counts to the results
        comparison_results["active_patterns_count"] = active_patterns[0]["pattern_count"] if active_patterns else 0
        comparison_results["reference_patterns_count"] = reference_patterns[0]["pattern_count"] if reference_patterns else 0
        
        return comparison_results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def deep_learn_from_multiple_repositories(self, repo_ids: List[int]) -> Dict[str, Any]:
        """[4.4.6] Deep learn from multiple reference repositories by analyzing cross-repository patterns.
        
        This method utilizes the enhanced graph synchronization capabilities to perform deep learning
        across multiple reference repositories, identifying common patterns that appear in high-quality
        repositories and can be considered industry best practices.
        """
        from utils.error_handling import AsyncErrorBoundary
        
        if len(repo_ids) < 2:
            raise ValueError("At least two repositories are required for cross-repository learning")
        
        # Process each repository individually first
        learning_results = []
        for repo_id in repo_ids:
            # Define operation for learning from a single repository
            async with AsyncErrorBoundary(
                f"learning_from_repository_{repo_id}", 
                error_types=(ProcessingError, DatabaseError, Neo4jError, ValueError)
            ):
                # Learn from individual repository first
                result = await self.learn_from_repository(repo_id)
                learning_results.append(result)
                
                # Ensure both code and pattern projections
                await graph_sync.ensure_projection(repo_id)
                await graph_sync.ensure_pattern_projection(repo_id)
        
        # Create cross-repository comparisons
        comparison_matrix = []
        for i, repo_id1 in enumerate(repo_ids):
            for repo_id2 in repo_ids[i+1:]:
                # Define operation for comparing repositories
                async with AsyncErrorBoundary(
                    f"comparing_repositories_{repo_id1}_{repo_id2}",
                    error_types=(Neo4jError, TransactionError, DatabaseError, ProcessingError)
                ):
                    # Compare each pair of repositories
                    comparison = await graph_sync.compare_repository_structures(
                        active_repo_id=repo_id1,
                        reference_repo_id=repo_id2
                    )
                    comparison_matrix.append({
                        "repo_id1": repo_id1,
                        "repo_id2": repo_id2,
                        "similarity_count": comparison.get("similarity_count", 0),
                        "similarities": comparison.get("similarities", [])
                    })
        
        # Extract common patterns across repositories
        common_patterns = await self._identify_common_patterns_across_repos(repo_ids)
        
        # Create cross-repository patterns in Neo4j
        await self._store_cross_repository_patterns(repo_ids, common_patterns)
        
        return {
            "repositories_processed": len(learning_results),
            "repository_comparisons": len(comparison_matrix),
            "common_patterns_identified": len(common_patterns),
            "cross_repository_learning_complete": True
        }
    
    @handle_async_errors(error_types=DatabaseError)
    async def _identify_common_patterns_across_repos(self, repo_ids: List[int]) -> List[Dict[str, Any]]:
        """Identify patterns that are common across multiple repositories."""
        common_patterns = []
        
        # Query for code patterns that are similar across repositories
        similar_code_patterns_query = """
        MATCH (p1:Pattern)-[:EXTRACTED_FROM]->(c1:Code {repo_id: $repo_id1})
        MATCH (p2:Pattern)-[:EXTRACTED_FROM]->(c2:Code {repo_id: $repo_id2})
        WHERE c1.language = c2.language AND p1.pattern_type = p2.pattern_type
        WITH p1, p2, c1.language AS language
        RETURN p1.pattern_id AS pattern_id1, 
               p2.pattern_id AS pattern_id2, 
               p1.pattern_type AS pattern_type,
               language
        LIMIT 100
        """
        
        # Check each pair of repositories for similar patterns
        for i, repo_id1 in enumerate(repo_ids):
            for repo_id2 in repo_ids[i+1:]:
                similar_patterns = await run_query(similar_code_patterns_query, {
                    "repo_id1": repo_id1,
                    "repo_id2": repo_id2
                })
                
                # Group by pattern type and language
                pattern_groups = {}
                for pattern in similar_patterns:
                    key = f"{pattern['pattern_type']}:{pattern['language']}"
                    if key not in pattern_groups:
                        pattern_groups[key] = []
                    pattern_groups[key].append(pattern)
                
                # Create common pattern entries
                for key, patterns in pattern_groups.items():
                    if len(patterns) >= 2:  # At least 2 similar patterns
                        pattern_type, language = key.split(":")
                        common_pattern = {
                            "pattern_type": pattern_type,
                            "language": language,
                            "source_patterns": patterns,
                            "repo_ids": [repo_id1, repo_id2],
                            "confidence": 0.8 + (0.05 * len(patterns))  # Higher confidence with more matches
                        }
                        common_patterns.append(common_pattern)
        
        return common_patterns
    
    @handle_async_errors(error_types=DatabaseError)
    async def _store_cross_repository_patterns(self, repo_ids: List[int], common_patterns: List[Dict[str, Any]]) -> None:
        """Store patterns that are common across multiple repositories."""
        # Create a special meta-repository node to represent the combined learning
        meta_repo_query = """
        MERGE (m:MetaRepository {id: $meta_id})
        SET m.repo_ids = $repo_ids,
            m.name = 'Cross-Repository Patterns',
            m.created_at = timestamp()
        """
        
        # Generate a unique ID for the meta repository (hash of sorted repo IDs)
        meta_id = hash(tuple(sorted(repo_ids))) & 0x7FFFFFFF  # Positive integer
        
        await run_query(meta_repo_query, {
            "meta_id": meta_id,
            "repo_ids": repo_ids
        })
        
        # Store each common pattern
        for i, pattern in enumerate(common_patterns):
            # Create pattern node
            pattern_query = """
            CREATE (p:CrossRepositoryPattern {
                id: $pattern_id,
                meta_id: $meta_id,
                pattern_type: $pattern_type,
                language: $language,
                confidence: $confidence
            })
            RETURN id(p) as node_id
            """
            
            pattern_result = await run_query(pattern_query, {
                "pattern_id": meta_id * 10000 + i,  # Generate unique ID
                "meta_id": meta_id,
                "pattern_type": pattern["pattern_type"],
                "language": pattern["language"],
                "confidence": pattern["confidence"]
            })
            
            if pattern_result:
                node_id = pattern_result[0]["node_id"]
                
                # Link to source patterns
                for source_pattern in pattern["source_patterns"]:
                    link_query = """
                    MATCH (cp:CrossRepositoryPattern) WHERE id(cp) = $node_id
                    MATCH (p:Pattern {pattern_id: $pattern_id, repo_id: $repo_id})
                    MERGE (cp)-[:DERIVED_FROM]->(p)
                    """
                    
                    # Link to first pattern
                    await run_query(link_query, {
                        "node_id": node_id,
                        "pattern_id": source_pattern["pattern_id1"],
                        "repo_id": pattern["repo_ids"][0]
                    })
                    
                    # Link to second pattern
                    await run_query(link_query, {
                        "node_id": node_id,
                        "pattern_id": source_pattern["pattern_id2"],
                        "repo_id": pattern["repo_ids"][1]
                    })
                
                # Link to meta repository
                meta_link_query = """
                MATCH (cp:CrossRepositoryPattern) WHERE id(cp) = $node_id
                MATCH (m:MetaRepository {id: $meta_id})
                MERGE (m)-[:CONTAINS_PATTERN]->(cp)
                """
                
                await run_query(meta_link_query, {
                    "node_id": node_id,
                    "meta_id": meta_id
                })
        
        log(f"Stored {len(common_patterns)} cross-repository patterns in meta-repository {meta_id}", level="info")
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_cross_repository_patterns(self, repo_ids: List[int]) -> Dict[str, Any]:
        """[4.4.7] Retrieve patterns common across multiple repositories."""
        # Generate meta-repository ID
        meta_id = hash(tuple(sorted(repo_ids))) & 0x7FFFFFFF
        
        # Check if meta-repository exists
        check_query = """
        MATCH (m:MetaRepository {id: $meta_id})
        RETURN m.created_at as created_at
        """
        
        meta_result = await run_query(check_query, {"meta_id": meta_id})
        
        if not meta_result:
            # If meta-repository doesn't exist, create it by running deep learning
            await self.deep_learn_from_multiple_repositories(repo_ids)
        
        # Retrieve cross-repository patterns
        patterns_query = """
        MATCH (m:MetaRepository {id: $meta_id})-[:CONTAINS_PATTERN]->(cp:CrossRepositoryPattern)
        OPTIONAL MATCH (cp)-[:DERIVED_FROM]->(p:Pattern)-[:EXTRACTED_FROM]->(c:Code)
        RETURN cp.id as pattern_id,
               cp.pattern_type as pattern_type,
               cp.language as language,
               cp.confidence as confidence,
               collect(distinct p.pattern_id) as source_patterns,
               collect(distinct c.file_path) as example_files
        """
        
        patterns = await run_query(patterns_query, {"meta_id": meta_id})
        
        return {
            "meta_repository_id": meta_id,
            "repository_ids": repo_ids,
            "pattern_count": len(patterns),
            "patterns": patterns
        }
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def apply_cross_repository_patterns(
        self,
        target_repo_id: int,
        repo_ids: List[int]
    ) -> Dict[str, Any]:
        """[4.4.8] Apply patterns common across reference repositories to a target repository.
        
        This method applies the deep learning patterns identified across multiple high-quality
        repositories to a target repository, providing high-confidence recommendations based
        on industry best practices.
        """
        # Get cross-repository patterns
        cross_patterns = await self.get_cross_repository_patterns(repo_ids)
        
        if not cross_patterns or not cross_patterns.get("patterns"):
            return {
                "target_repo_id": target_repo_id,
                "recommendations_count": 0,
                "status": "No cross-repository patterns found"
            }
        
        # Analyze target repository
        target_analysis = await self.code_understanding.analyze_codebase(target_repo_id)
        
        # Generate recommendations
        recommendations = []
        
        # Get target repository languages
        lang_query = """
        SELECT DISTINCT language FROM file_metadata
        WHERE repo_id = $repo_id AND language IS NOT NULL
        """
        
        languages = await query(lang_query, {"repo_id": target_repo_id})
        target_languages = [lang["language"] for lang in languages]
        
        # Filter patterns by languages used in target
        for pattern in cross_patterns.get("patterns", []):
            if pattern["language"] in target_languages:
                # Find potential target files
                files_query = """
                SELECT file_path FROM file_metadata
                WHERE repo_id = $repo_id AND language = $language
                LIMIT 5
                """
                
                target_files = await query(files_query, {
                    "repo_id": target_repo_id,
                    "language": pattern["language"]
                })
                
                for file in target_files:
                    recommendation = {
                        "pattern_id": pattern["pattern_id"],
                        "pattern_type": pattern["pattern_type"],
                        "language": pattern["language"],
                        "target_file": file["file_path"],
                        "recommendation": f"Apply cross-repository best practice pattern",
                        "confidence": pattern["confidence"],
                        "example_files": pattern["example_files"][:3] if pattern.get("example_files") else [],
                        "is_cross_repository": True
                    }
                    recommendations.append(recommendation)
        
        return {
            "target_repo_id": target_repo_id,
            "reference_repos": repo_ids,
            "recommendations_count": len(recommendations),
            "recommendations": recommendations,
            "status": "success"
        }

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def update_patterns_for_file(self, repo_id: int, file_path: str) -> Dict[str, Any]:
        """[4.4.9] Update patterns for a specific file in a repository.
        
        This method extracts patterns from a single file and updates them in the database,
        useful for incremental updates without reprocessing the entire repository.
        
        Args:
            repo_id: Repository ID
            file_path: Path to the file to update
            
        Returns:
            Dict with update results
        """
        from utils.error_handling import AsyncErrorBoundary
        from parsers.pattern_processor import pattern_processor
        
        # Define a helper function for embedding creation
        async def create_embedding(pattern_text):
            async with AsyncErrorBoundary("pattern_embedding"):
                embedding = await self.embedder.embed(pattern_text)
                return embedding.tolist() if hasattr(embedding, 'tolist') else None
            return None  # Return None if AsyncErrorBoundary catches an exception
        
        # Use AsyncErrorBoundary for the main operation
        async with AsyncErrorBoundary("update_file_patterns", error_types=(Exception,)):
            # Get file content and language
            file_query = """
                SELECT file_content, language 
                FROM file_metadata 
                WHERE repo_id = $repo_id AND file_path = $file_path
            """
            file_result = await query(file_query, {"repo_id": repo_id, "file_path": file_path})
            
            if not file_result:
                return {"status": "error", "message": f"File not found: {file_path}"}
            
            file_content = file_result[0]["file_content"]
            language = file_result[0]["language"]
            
            # Delete existing patterns for this file
            delete_query = """
                DELETE FROM code_patterns
                WHERE repo_id = $repo_id AND file_path = $file_path
            """
            await query(delete_query, {"repo_id": repo_id, "file_path": file_path})
            
            # Extract patterns using pattern processor
            patterns = pattern_processor.extract_repository_patterns(file_path, file_content, language)
            
            # Store patterns
            new_patterns = []
            for pattern in patterns:
                # Create embedding for the pattern
                pattern_text = pattern.get("content", "")
                if pattern_text:
                    # Use the helper function with AsyncErrorBoundary
                    embedding_list = create_embedding(pattern_text)
                    
                    # Store pattern in database
                    pattern_query = """
                        INSERT INTO code_patterns (
                            repo_id, file_path, pattern_type, content, 
                            language, confidence, example_usage, embedding
                        ) VALUES (
                            $repo_id, $file_path, $pattern_type, $content,
                            $language, $confidence, $example_usage, $embedding
                        )
                        RETURNING id
                    """
                    
                    pattern_id = await query(pattern_query, {
                        "repo_id": repo_id,
                        "file_path": file_path,
                        "pattern_type": pattern.get("pattern_type", "code_structure"),
                        "content": pattern_text,
                        "language": language,
                        "confidence": pattern.get("confidence", 0.7),
                        "example_usage": pattern.get("content", ""),
                        "embedding": embedding_list
                    })
                    
                    if pattern_id:
                        # Also store in Neo4j
                        await self.neo4j_tools.store_pattern_node({
                            "pattern_id": pattern_id[0]["id"],
                            "repo_id": repo_id,
                            "file_path": file_path,
                            "pattern_type": pattern.get("pattern_type", "code_structure"),
                            "language": language,
                            "confidence": pattern.get("confidence", 0.7)
                        })
                        
                        new_patterns.append(pattern_id[0]["id"])
            
            # Update graph projection if patterns were added
            if new_patterns:
                await graph_sync.invalidate_pattern_projection(repo_id)
                await graph_sync.ensure_pattern_projection(repo_id)
            
            return {
                "status": "success",
                "file_path": file_path,
                "patterns_updated": len(new_patterns),
                "pattern_ids": new_patterns
            }
        
        # If AsyncErrorBoundary catches an exception, we'll return an error status
        return {"status": "error", "message": "Failed to update patterns for file"}


# Create a singleton instance
reference_learning = ReferenceRepositoryLearning() 