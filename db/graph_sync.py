"""Graph synchronization and projection coordination."""

import asyncio
from typing import Optional, Set, Dict
from utils.logger import log
from db.neo4j_ops import run_query, driver
from utils.cache import create_cache

# Cache for graph states
graph_cache = create_cache("graph_state", ttl=300)

class GraphSyncCoordinator:
    """Coordinates graph operations and projections."""
    
    def __init__(self):
        self._lock = asyncio.Lock()
        self._active_projections: Set[str] = set()
        
    async def ensure_projection(self, repo_id: int) -> bool:
        """Ensures graph projection exists and is up to date."""
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            try:
                # Check if projection exists and is valid
                if await self._is_projection_valid(projection_name):
                    return True
                
                # Create or update projection
                await self._create_projection(repo_id, projection_name)
                self._active_projections.add(projection_name)
                return True
                
            except Exception as e:
                log(f"Error ensuring graph projection: {e}", level="error")
                return False
    
    async def invalidate_projection(self, repo_id: int) -> None:
        """Invalidates existing projection for repository."""
        projection_name = f"code-repo-{repo_id}"
        
        async with self._lock:
            try:
                if projection_name in self._active_projections:
                    await self._drop_projection(projection_name)
                    self._active_projections.remove(projection_name)
                await graph_cache.clear_pattern_async(f"graph:{repo_id}:*")
            except Exception as e:
                log(f"Error invalidating projection: {e}", level="error")
    
    async def _is_projection_valid(self, projection_name: str) -> bool:
        """Checks if projection exists and is valid."""
        try:
            result = await graph_cache.get_async(f"projection:{projection_name}")
            if result:
                return True
            
            query = """
            CALL gds.graph.exists($projection)
            YIELD exists
            """
            response = run_query(query, {"projection": projection_name})
            exists = response[0].get("exists", False)
            
            if exists:
                await graph_cache.set_async(f"projection:{projection_name}", True)
            
            return exists
            
        except Exception as e:
            log(f"Error checking projection validity: {e}", level="error")
            return False
    
    async def _create_projection(self, repo_id: int, projection_name: str) -> None:
        """Creates or updates graph projection."""
        projection_query = f"""
        CALL gds.graph.project.cypher(
            '{projection_name}',
            'MATCH (n:Code) WHERE n.repo_id = $repo_id RETURN id(n) AS id, labels(n) AS labels',
            'MATCH (n:Code)-[r]->(m:Code) WHERE n.repo_id = $repo_id AND m.repo_id = $repo_id 
             RETURN id(n) AS source, id(m) AS target, type(r) AS type',
            {{
                validateRelationships: false
            }}
        )
        """
        try:
            run_query(projection_query, {"repo_id": repo_id})
            await graph_cache.set_async(f"projection:{projection_name}", True)
            log(f"Created graph projection: {projection_name}", level="info")
        except Exception as e:
            log(f"Error creating graph projection: {e}", level="error")
            raise
    
    async def _drop_projection(self, projection_name: str) -> None:
        """Drops existing graph projection."""
        try:
            query = "CALL gds.graph.drop($projection)"
            run_query(query, {"projection": projection_name})
            await graph_cache.clear_pattern_async(f"projection:{projection_name}")
            log(f"Dropped graph projection: {projection_name}", level="info")
        except Exception as e:
            log(f"Error dropping projection: {e}", level="error")

# Global instance
graph_sync = GraphSyncCoordinator() 