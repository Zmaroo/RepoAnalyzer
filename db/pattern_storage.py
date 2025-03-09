"""Pattern storage coordination system.

This module provides centralized coordination for pattern storage operations,
ensuring consistent handling of patterns across the system.
"""

from typing import Dict, List, Any, Optional, Set
import asyncio
from dataclasses import dataclass
from utils.logger import log
from utils.error_handling import (
    handle_async_errors,
    AsyncErrorBoundary,
    DatabaseError,
    ProcessingError,
    ErrorSeverity
)
from db.transaction import transaction_scope
from db.upsert_ops import UpsertCoordinator
from db.graph_sync import graph_sync
from utils.cache import UnifiedCache
from utils.shutdown import register_shutdown_handler
from db.connection import connection_manager
from db.retry_utils import RetryManager, RetryConfig

@dataclass
class PatternStorageMetrics:
    """Metrics for pattern storage operations."""
    total_patterns: int = 0
    code_patterns: int = 0
    doc_patterns: int = 0
    arch_patterns: int = 0
    pattern_relationships: int = 0
    last_update: float = 0.0

class PatternStorage:
    """Storage for code patterns with optimized connection handling."""
    
    def __init__(self):
        self._initialized = False
        self._pool = None
        self._retry_manager = None
        self._pending_tasks = set()
        self._lock = asyncio.Lock()
    
    async def initialize(self):
        """Initialize pattern storage."""
        if self._initialized:
            return True
            
        try:
            async with AsyncErrorBoundary("pattern_storage_initialization"):
                # Initialize connection pool
                self._pool = await connection_manager.create_pool(
                    min_size=5,
                    max_size=20,
                    max_queries=50000,
                    setup=["SET application_name = 'pattern_storage'"]
                )
                
                # Initialize retry manager
                self._retry_manager = RetryManager(
                    RetryConfig(max_retries=3, base_delay=1.0, max_delay=10.0)
                )
                
                self._initialized = True
                return True
        except Exception as e:
            await log(f"Error initializing pattern storage: {e}", level="error")
            return False
    
    async def store_pattern(self, pattern: Dict[str, Any], repo_id: Optional[int] = None) -> int:
        """Store a pattern with retry mechanism."""
        if not self._initialized:
            await self.initialize()
            
        async def _store():
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    # Store pattern
                    pattern_id = await conn.fetchval("""
                        INSERT INTO patterns (
                            repo_id, pattern_type, content, language,
                            confidence, metadata, embedding
                        ) VALUES (
                            $1, $2, $3, $4, $5, $6, $7
                        ) RETURNING id
                    """, repo_id, pattern["type"], pattern["content"],
                        pattern.get("language"), pattern.get("confidence", 0.8),
                        pattern.get("metadata"), pattern.get("embedding"))
                    
                    # Store relationships if present
                    if "relationships" in pattern:
                        for rel in pattern["relationships"]:
                            await conn.execute("""
                                INSERT INTO pattern_relationships (
                                    source_id, target_id, relationship_type,
                                    metadata
                                ) VALUES ($1, $2, $3, $4)
                            """, pattern_id, rel["target_id"],
                                rel["type"], rel.get("metadata"))
                    
                    return pattern_id
        
        try:
            return await self._retry_manager.with_retry(_store)
        except Exception as e:
            await log(f"Error storing pattern after retries: {e}", level="error")
            raise
    
    async def get_pattern(self, pattern_id: int) -> Optional[Dict[str, Any]]:
        """Get a pattern by ID with retry mechanism."""
        if not self._initialized:
            await self.initialize()
            
        async def _get():
            async with self._pool.acquire() as conn:
                async with conn.transaction():
                    pattern = await conn.fetchrow("""
                        SELECT * FROM patterns WHERE id = $1
                    """, pattern_id)
                    
                    if pattern:
                        # Get relationships
                        relationships = await conn.fetch("""
                            SELECT * FROM pattern_relationships
                            WHERE source_id = $1
                        """, pattern_id)
                        
                        return {
                            **dict(pattern),
                            "relationships": [dict(r) for r in relationships]
                        }
                    return None
        
        try:
            return await self._retry_manager.with_retry(_get)
        except Exception as e:
            await log(f"Error getting pattern after retries: {e}", level="error")
            return None
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            if self._pool:
                await self._pool.close()
            if self._retry_manager:
                await self._retry_manager.cleanup()
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
            self._initialized = False
        except Exception as e:
            await log(f"Error cleaning up pattern storage: {e}", level="error")

class PatternStorageCoordinator:
    """Coordinates pattern storage operations across the system."""
    
    def __init__(self):
        """Initialize the coordinator."""
        self._initialized = False
        self._pending_tasks: Set[asyncio.Task] = set()
        self._lock = asyncio.Lock()
        self._cache = None
        self._metrics = PatternStorageMetrics()
        self._upsert_coordinator = UpsertCoordinator()
    
    async def ensure_initialized(self):
        """Ensure the coordinator is initialized."""
        if not self._initialized:
            raise DatabaseError("PatternStorageCoordinator not initialized. Use create() to initialize.")
        return True
    
    @classmethod
    async def create(cls) -> 'PatternStorageCoordinator':
        """Create and initialize a pattern storage coordinator instance."""
        instance = cls()
        try:
            async with AsyncErrorBoundary("pattern storage coordinator initialization"):
                # Initialize cache
                instance._cache = UnifiedCache("pattern_storage")
                
                # Register shutdown handler
                register_shutdown_handler(instance.cleanup)
                
                instance._initialized = True
                await log("Pattern storage coordinator initialized", level="info")
                return instance
        except Exception as e:
            await log(f"Error initializing pattern storage coordinator: {e}", level="error")
            await instance.cleanup()
            raise DatabaseError(f"Failed to initialize pattern storage coordinator: {e}")
    
    @handle_async_errors(error_types=(DatabaseError, ProcessingError))
    async def store_patterns(
        self,
        repo_id: int,
        patterns: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, List[int]]:
        """Store patterns of different types for a repository."""
        pattern_ids = {
            "code": [],
            "doc": [],
            "arch": []
        }
        
        async with transaction_scope() as txn:
            # Store code patterns
            if "code" in patterns:
                for pattern in patterns["code"]:
                    pattern_id = await self._store_code_pattern(txn, repo_id, pattern)
                    if pattern_id:
                        pattern_ids["code"].append(pattern_id)
            
            # Store documentation patterns
            if "doc" in patterns:
                for pattern in patterns["doc"]:
                    pattern_id = await self._store_doc_pattern(txn, repo_id, pattern)
                    if pattern_id:
                        pattern_ids["doc"].append(pattern_id)
            
            # Store architecture patterns
            if "arch" in patterns:
                for pattern in patterns["arch"]:
                    pattern_id = await self._store_arch_pattern(txn, repo_id, pattern)
                    if pattern_id:
                        pattern_ids["arch"].append(pattern_id)
            
            # Update pattern relationships
            if any(pattern_ids.values()):
                await self._update_pattern_relationships(txn, repo_id, pattern_ids)
            
            # Update metrics
            await self._update_metrics(pattern_ids)
        
        return pattern_ids
    
    async def _store_code_pattern(
        self,
        txn,
        repo_id: int,
        pattern: Dict[str, Any]
    ) -> Optional[int]:
        """Store a code pattern with tree-sitter support."""
        pattern_data = {
            "repo_id": repo_id,
            "file_path": pattern["file_path"],
            "language": pattern["language"],
            "pattern_type": pattern["pattern_type"],
            "content": pattern["content"],
            "confidence": pattern.get("confidence", 0.7),
            "complexity": pattern.get("complexity"),
            "dependencies": pattern.get("dependencies", []),
            "documentation": pattern.get("documentation"),
            "metadata": pattern.get("metadata", {}),
            "embedding": pattern.get("embedding"),
            "tree_sitter_type": pattern.get("tree_sitter_type"),
            "tree_sitter_language": pattern.get("tree_sitter_language"),
            "tree_sitter_metrics": pattern.get("tree_sitter_metrics", {})
        }
        
        # Use upsert coordinator
        pattern_id = await self._upsert_coordinator.store_parsed_content(
            repo_id=repo_id,
            file_path=pattern["file_path"],
            ast={"elements": pattern.get("elements", {})},
            features=pattern_data
        )
        
        if pattern_id:
            # Store in Neo4j with tree-sitter data
            await graph_sync.store_pattern_node({
                "repo_id": repo_id,
                "pattern_id": pattern_id,
                "pattern_type": pattern["pattern_type"],
                "language": pattern["language"],
                "file_path": pattern["file_path"],
                "embedding": pattern.get("embedding"),
                "elements": pattern.get("elements", {}),
                "tree_sitter_type": pattern.get("tree_sitter_type"),
                "tree_sitter_language": pattern.get("tree_sitter_language"),
                "tree_sitter_metrics": pattern.get("tree_sitter_metrics", {})
            })
        
        return pattern_id
    
    async def _store_doc_pattern(
        self,
        txn,
        repo_id: int,
        pattern: Dict[str, Any]
    ) -> Optional[int]:
        """Store a documentation pattern."""
        pattern_data = {
            "repo_id": repo_id,
            "file_path": f"patterns/{pattern['doc_type']}/pattern_{pattern.get('id', 'new')}.md",
            "doc_type": pattern["doc_type"],
            "pattern_type": pattern["pattern_type"],
            "content": "\n".join(pattern.get("samples", [])),
            "confidence": pattern.get("confidence", 0.7),
            "structure": pattern.get("structure", {}),
            "metadata": pattern.get("metadata", {}),
            "embedding": pattern.get("embedding")
        }
        
        # Use upsert coordinator
        pattern_id = await self._upsert_coordinator.upsert_doc(**pattern_data)
        
        if pattern_id:
            # Store in Neo4j
            await graph_sync.store_pattern_node({
                "repo_id": repo_id,
                "pattern_id": pattern_id,
                "pattern_type": pattern["pattern_type"],
                "doc_type": pattern["doc_type"],
                "file_path": pattern_data["file_path"],
                "embedding": pattern.get("embedding"),
                "structure": pattern.get("structure", {})
            })
        
        return pattern_id
    
    async def _store_arch_pattern(
        self,
        txn,
        repo_id: int,
        pattern: Dict[str, Any]
    ) -> Optional[int]:
        """Store an architecture pattern."""
        pattern_data = {
            "repo_id": repo_id,
            "pattern_type": pattern["pattern_type"],
            "structure": pattern.get("structure", {}),
            "dependencies": pattern.get("dependencies", {}),
            "confidence": pattern.get("confidence", 0.7),
            "metadata": pattern.get("metadata", {}),
            "embedding": pattern.get("embedding")
        }
        
        # Use upsert coordinator
        pattern_id = await self._upsert_coordinator.store_parsed_content(
            repo_id=repo_id,
            file_path=f"architecture/{pattern['pattern_type']}.json",
            ast=pattern_data,
            features=pattern_data
        )
        
        if pattern_id:
            # Store in Neo4j
            await graph_sync.store_pattern_node({
                "repo_id": repo_id,
                "pattern_id": pattern_id,
                "pattern_type": pattern["pattern_type"],
                "structure": pattern.get("structure", {}),
                "dependencies": pattern.get("dependencies", {}),
                "embedding": pattern.get("embedding")
            })
        
        return pattern_id
    
    async def _update_pattern_relationships(
        self,
        txn,
        repo_id: int,
        pattern_ids: Dict[str, List[int]]
    ) -> None:
        """Update pattern relationships in Neo4j."""
        # Link patterns to repository
        await graph_sync.link_patterns_to_repository(repo_id, [
            pattern_id for ids in pattern_ids.values() for pattern_id in ids
        ])
        
        # Update pattern projection
        await graph_sync.invalidate_pattern_projection(repo_id)
        await graph_sync.ensure_pattern_projection(repo_id)
    
    async def _update_metrics(self, pattern_ids: Dict[str, List[int]]) -> None:
        """Update storage metrics."""
        self._metrics.total_patterns += sum(len(ids) for ids in pattern_ids.values())
        self._metrics.code_patterns += len(pattern_ids["code"])
        self._metrics.doc_patterns += len(pattern_ids["doc"])
        self._metrics.arch_patterns += len(pattern_ids["arch"])
        self._metrics.pattern_relationships += sum(len(ids) for ids in pattern_ids.values())
        self._metrics.last_update = asyncio.get_event_loop().time()
    
    @handle_async_errors(error_types=(DatabaseError, ProcessingError))
    async def get_patterns(
        self,
        repo_id: int,
        pattern_type: Optional[str] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Get patterns for a repository."""
        patterns = {
            "code": [],
            "doc": [],
            "arch": []
        }
        
        async with transaction_scope() as txn:
            # Get code patterns
            if not pattern_type or pattern_type == "code":
                patterns["code"] = await self._get_code_patterns(txn, repo_id)
            
            # Get documentation patterns
            if not pattern_type or pattern_type == "doc":
                patterns["doc"] = await self._get_doc_patterns(txn, repo_id)
            
            # Get architecture patterns
            if not pattern_type or pattern_type == "arch":
                patterns["arch"] = await self._get_arch_patterns(txn, repo_id)
        
        return patterns
    
    async def _get_code_patterns(
        self,
        txn,
        repo_id: int
    ) -> List[Dict[str, Any]]:
        """Get code patterns from database."""
        query = """
            SELECT p.*, c.file_path, c.language
            FROM code_patterns p
            JOIN code_snippets c ON c.id = p.code_id
            WHERE c.repo_id = $1
        """
        return await txn.fetch(query, repo_id)
    
    async def _get_doc_patterns(
        self,
        txn,
        repo_id: int
    ) -> List[Dict[str, Any]]:
        """Get documentation patterns from database."""
        query = """
            SELECT d.*, r.repo_id
            FROM repo_docs d
            JOIN repo_doc_relations r ON d.id = r.doc_id
            WHERE r.repo_id = $1 AND d.doc_type = 'pattern'
        """
        return await txn.fetch(query, repo_id)
    
    async def _get_arch_patterns(
        self,
        txn,
        repo_id: int
    ) -> List[Dict[str, Any]]:
        """Get architecture patterns from database."""
        query = """
            SELECT c.*
            FROM code_snippets c
            WHERE c.repo_id = $1 
            AND c.file_path LIKE 'architecture/%'
        """
        return await txn.fetch(query, repo_id)
    
    @handle_async_errors(error_types=(DatabaseError, ProcessingError))
    async def update_patterns_for_file(
        self,
        repo_id: int,
        file_path: str,
        patterns: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update patterns for a specific file."""
        async with transaction_scope() as txn:
            # Delete existing patterns
            await self._delete_file_patterns(txn, repo_id, file_path)
            
            # Store new patterns
            pattern_ids = await self.store_patterns(repo_id, {
                "code": patterns
            })
            
            return {
                "status": "success",
                "file_path": file_path,
                "patterns_updated": len(pattern_ids["code"]),
                "pattern_ids": pattern_ids["code"]
            }
    
    async def _delete_file_patterns(
        self,
        txn,
        repo_id: int,
        file_path: str
    ) -> None:
        """Delete patterns for a specific file."""
        query = """
            DELETE FROM code_patterns
            WHERE repo_id = $1 AND file_path = $2
        """
        await txn.execute(query, repo_id, file_path)
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            # Cancel all pending tasks
            if self._pending_tasks:
                for task in self._pending_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._pending_tasks, return_exceptions=True)
                self._pending_tasks.clear()
            
            # Clear cache
            if self._cache:
                await self._cache.clear()
            
            self._initialized = False
            await log("Pattern storage coordinator cleaned up", level="info")
        except Exception as e:
            await log(f"Error cleaning up pattern storage coordinator: {e}", level="error")
            raise DatabaseError(f"Failed to cleanup pattern storage coordinator: {e}")

# Create global instance
pattern_storage = None

async def get_pattern_storage() -> PatternStorageCoordinator:
    """Get the global pattern storage coordinator instance."""
    global pattern_storage
    if not pattern_storage:
        pattern_storage = await PatternStorageCoordinator.create()
    return pattern_storage 