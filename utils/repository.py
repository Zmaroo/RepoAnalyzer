"""
Repository management utilities for the RepoAnalyzer project.

This module provides functions for working with code repositories,
including accessing repository metadata, tracking repository access patterns,
and managing repository-specific caching.
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set, Tuple
from utils.logger import log
from utils.error_handling import handle_async_errors, AsyncErrorBoundary
from utils.cache import cache_coordinator

# Try to import database modules
try:
    from db.psql import query, execute
    from db.transaction import transaction_scope
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    log("Database modules not available, using fallback repository data", level="warning")

class RepositoryAccessTracker:
    """Tracks repository access patterns for analytics and cache warming."""
    
    def __init__(self):
        self._access_history = {}
        self._access_timestamps = {}
        self._lock = asyncio.Lock()
    
@handle_async_errors(error_types=(Exception,))
    async def record_access(self, repo_id: int, reason: str = "general"):
        """Record an access to a repository."""
        async with self._lock:
            if repo_id not in self._access_history:
                self._access_history[repo_id] = 0
                self._access_timestamps[repo_id] = []
                
            self._access_history[repo_id] += 1
            self._access_timestamps[repo_id].append({
                "timestamp": datetime.now().isoformat(),
                "reason": reason
            })
            
            # Keep only the last 20 access records
            if len(self._access_timestamps[repo_id]) > 20:
                self._access_timestamps[repo_id] = self._access_timestamps[repo_id][-20:]
@handle_async_errors(error_types=(Exception,))
    
    async def get_most_accessed(self, limit: int = 10) -> List[int]:
        """Get the most frequently accessed repositories."""
        async with self._lock:
            # Sort by access count
            sorted_repos = sorted(
                self._access_history.items(),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Return just the repo IDs
@handle_async_errors(error_types=(Exception,))
            return [repo_id for repo_id, _ in sorted_repos[:limit]]
    
    async def get_recently_accessed(self, limit: int = 10) -> List[int]:
        """Get the most recently accessed repositories."""
        async with self._lock:
            # Create a list of (repo_id, last_access_time)
            recent_access = []
            
            for repo_id, timestamps in self._access_timestamps.items():
                if timestamps:
                    # Get the most recent timestamp
                    recent_access.append((
                        repo_id, 
                        max(t["timestamp"] for t in timestamps)
                    ))
            
            # Sort by timestamp (most recent first)
            sorted_recent = sorted(
                recent_access,
                key=lambda x: x[1],
                reverse=True
            )
            
            # Return just the repo IDs
            return [repo_id for repo_id, _ in sorted_recent[:limit]]

# Global instance of the access tracker
repo_access_tracker = RepositoryAccessTracker()

@handle_async_errors
async def get_repository_by_id(repo_id: int) -> Optional[Dict[str, Any]]:
    """
    Get repository information by ID.
    
    Args:
        repo_id: The repository ID
        
    Returns:
        Repository data dictionary or None if not found
    """
    if not DB_AVAILABLE:
        # Fallback data for testing
        return {
            "id": repo_id,
            "name": f"repository_{repo_id}",
            "path": f"/path/to/repo_{repo_id}",
            "last_indexed": datetime.now().isoformat()
        }
    
    # Use AsyncErrorBoundary for database query
    async with AsyncErrorBoundary(operation_name=f"get_repository_by_id({repo_id})"):
        sql = "SELECT * FROM repositories WHERE id = $1"
        results = await query(sql, repo_id)
        
        if results and len(results) > 0:
            # Record this access
            await repo_access_tracker.record_access(repo_id, "direct_lookup")
            return dict(results[0])
        
        return None

@handle_async_errors
async def get_recent_repositories(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Get a list of recently accessed repositories.
    
    Args:
        limit: Maximum number of repositories to return
        
    Returns:
        List of repository data dictionaries
    """
    repo_ids = await repo_access_tracker.get_recently_accessed(limit)
    
    # If no recent activity, try from database
    if not repo_ids and DB_AVAILABLE:
        async with AsyncErrorBoundary(operation_name="get_recent_repositories_from_db"):
            sql = """
                SELECT * FROM repositories 
                ORDER BY last_accessed DESC 
                LIMIT $1
            """
            results = await query(sql, limit)
            return [dict(row) for row in results] if results else []
    
    # Otherwise get details for the recent repos
    repositories = []
    for repo_id in repo_ids:
        repo = await get_repository_by_id(repo_id)
        if repo:
            repositories.append(repo)
    
    # If we still don't have enough, generate some fallback data
    if not repositories and not DB_AVAILABLE:
        # Fallback data for testing
        repositories = [
            {
                "id": i,
                "name": f"repository_{i}",
                "path": f"/path/to/repo_{i}",
                "last_indexed": datetime.now().isoformat()
            }
            for i in range(1, limit + 1)
        ]
    
    return repositories

@handle_async_errors
async def update_repository_access(repo_id: int) -> bool:
    """
    Update the last_accessed timestamp for a repository.
    
    Args:
        repo_id: The repository ID
        
    Returns:
        True if successful, False otherwise
    """
    # Always record in our local tracker
    await repo_access_tracker.record_access(repo_id, "update_access")
    
    if not DB_AVAILABLE:
        return True
    
    # Update in database
    async with AsyncErrorBoundary(operation_name=f"update_repository_access({repo_id})"):
        async with transaction_scope() as txn:
            sql = """
                UPDATE repositories 
                SET last_accessed = NOW() 
                WHERE id = $1
            """
            await execute(sql, repo_id)
            await txn.track_repo_change(repo_id)
            
            # Also warm the cache for this repository
            await cache_coordinator.warm_key(f"repo:{repo_id}:metadata")
            
            return True

@handle_async_errors
async def get_repository_stats(repo_id: int) -> Dict[str, Any]:
    """
    Get statistics for a repository.
    
    Args:
        repo_id: The repository ID
        
    Returns:
        Dictionary of repository statistics
    """
    if not DB_AVAILABLE:
        # Fallback data
        return {
            "repo_id": repo_id,
            "file_count": 100,
            "file_types": {
                "py": 50,
                "js": 30,
                "other": 20
            },
            "total_lines": 10000,
            "last_indexed": datetime.now().isoformat()
        }
    
    async with AsyncErrorBoundary(operation_name=f"get_repository_stats({repo_id})"):
        # Get file statistics
        file_stats_sql = """
            SELECT 
                COUNT(*) as file_count,
                SUM(line_count) as total_lines
            FROM repo_files 
            WHERE repo_id = $1
        """
        file_stats = await query(file_stats_sql, repo_id)
        
        # Get file type breakdown
        file_types_sql = """
            SELECT 
                file_extension,
                COUNT(*) as count
            FROM repo_files 
            WHERE repo_id = $1
            GROUP BY file_extension
            ORDER BY count DESC
        """
        file_types = await query(file_types_sql, repo_id)
        
        # Record this access
        await repo_access_tracker.record_access(repo_id, "statistics")
        
        return {
            "repo_id": repo_id,
            "file_count": file_stats[0]["file_count"] if file_stats else 0,
            "total_lines": file_stats[0]["total_lines"] if file_stats else 0,
            "file_types": {
                row["file_extension"]: row["count"] 
                for row in file_types
            } if file_types else {},
            "last_indexed": datetime.now().isoformat()
        }

# Initialize module
@handle_errors(error_types=(Exception,))
def initialize():
    """Initialize the repository module."""
    log("Repository management module initialized", level="info")
    
# Call initialize
initialize() 