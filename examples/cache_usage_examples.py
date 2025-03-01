"""Examples demonstrating the enhanced cache features.

This module shows practical examples of:
1. Setting up caches with proper TTL values
2. Registering warmup functions for database queries
3. Using adaptive TTL for different types of queries
4. Monitoring cache performance
"""

import asyncio
import os
from typing import List, Dict, Any, Optional

from utils.cache import create_cache, UnifiedCache
from utils.cache_analytics import cache_analytics
from utils.logger import log
from utils.error_handling import handle_async_errors

# Create example directory if it doesn't exist
os.makedirs("examples", exist_ok=True)

# Example caches for different data types
repository_cache = create_cache("repository", ttl=3600, adaptive_ttl=True)  # 1 hour default
user_cache = create_cache("user", ttl=1800, adaptive_ttl=True)  # 30 minutes default
search_cache = create_cache("search", ttl=600, adaptive_ttl=True)  # 10 minutes default

# Mock database interface (in a real app, this would connect to a real database)
class MockDatabase:
    """Mock database for demonstration purposes."""
    
    def __init__(self):
        """Initialize with some example data."""
        self.repositories = {
            "repo1": {"id": 1, "name": "Repository 1", "stars": 100},
            "repo2": {"id": 2, "name": "Repository 2", "stars": 200},
            "repo3": {"id": 3, "name": "Repository 3", "stars": 300},
        }
        
        self.users = {
            "user1": {"id": 1, "name": "User 1", "email": "user1@example.com"},
            "user2": {"id": 2, "name": "User 2", "email": "user2@example.com"},
        }
        
        self.files = {
            "file1": {"id": 1, "content": "Example content 1", "repo_id": 1},
            "file2": {"id": 2, "content": "Example content 2", "repo_id": 1},
            "file3": {"id": 3, "content": "Example content 3", "repo_id": 2},
        }
    
    async def get_repositories(self, repo_ids: List[int]) -> Dict[int, Dict]:
        """Get repositories by IDs."""
        await asyncio.sleep(0.1)  # Simulate DB latency
        result = {}
        for repo_id in repo_ids:
            for repo_key, repo_data in self.repositories.items():
                if repo_data["id"] == repo_id:
                    result[repo_id] = repo_data
        return result
    
    async def get_users(self, user_ids: List[int]) -> Dict[int, Dict]:
        """Get users by IDs."""
        await asyncio.sleep(0.1)  # Simulate DB latency
        result = {}
        for user_id in user_ids:
            for user_key, user_data in self.users.items():
                if user_data["id"] == user_id:
                    result[user_id] = user_data
        return result
    
    async def search_files(self, query: str) -> List[Dict]:
        """Search files by content."""
        await asyncio.sleep(0.2)  # Simulate search latency
        results = []
        for file_key, file_data in self.files.items():
            if query.lower() in file_data["content"].lower():
                results.append(file_data)
        return results

# Create a mock database instance
db = MockDatabase()

# Example warmup functions for each cache
@handle_async_errors()
async def warmup_repository_cache(repo_ids: List[str]) -> Dict[str, Any]:
    """Fetch repository data for cache warmup."""
    try:
        # Convert string IDs to integers
        int_ids = [int(repo_id) for repo_id in repo_ids]
        repositories = await db.get_repositories(int_ids)
        # Convert integer keys back to strings for cache
        return {str(k): v for k, v in repositories.items()}
    except Exception as e:
        log(f"Error in repository warmup: {e}", level="error")
        return {}

@handle_async_errors()
async def warmup_user_cache(user_ids: List[str]) -> Dict[str, Any]:
    """Fetch user data for cache warmup."""
    try:
        # Convert string IDs to integers
        int_ids = [int(user_id) for user_id in user_ids]
        users = await db.get_users(int_ids)
        # Convert integer keys back to strings for cache
        return {str(k): v for k, v in users.items()}
    except Exception as e:
        log(f"Error in user warmup: {e}", level="error")
        return {}

@handle_async_errors()
async def warmup_search_cache(queries: List[str]) -> Dict[str, Any]:
    """Fetch search results for cache warmup."""
    try:
        results = {}
        for query in queries:
            results[query] = await db.search_files(query)
        return results
    except Exception as e:
        log(f"Error in search warmup: {e}", level="error")
        return {}

# Register warmup functions
def register_warmup_functions():
    """Register all warmup functions with the cache analytics."""
    cache_analytics.register_warmup_function("repository", warmup_repository_cache)
    cache_analytics.register_warmup_function("user", warmup_user_cache)
    cache_analytics.register_warmup_function("search", warmup_search_cache)
    log("Registered warmup functions for all caches", level="info")

# Example repository service using caching
class RepositoryService:
    """Service for repository operations with caching."""
    
    @handle_async_errors()
    async def get_repository(self, repo_id: int) -> Optional[Dict]:
        """Get a repository by ID with caching."""
        # Try to get from cache first
        cache_key = str(repo_id)
        cached_repo = await repository_cache.get_async(cache_key)
        
        if cached_repo:
            log(f"Cache hit for repository {repo_id}", level="debug")
            return cached_repo
        
        # If not in cache, fetch from database
        log(f"Cache miss for repository {repo_id}", level="debug")
        repositories = await db.get_repositories([repo_id])
        
        if repo_id in repositories:
            repo_data = repositories[repo_id]
            # Cache the result
            await repository_cache.set_async(cache_key, repo_data)
            return repo_data
        
        return None
    
    @handle_async_errors()
    async def search_repositories(self, query: str) -> List[Dict]:
        """Search repositories with caching."""
        # For search queries, use a shorter TTL
        cache_key = f"search:{query}"
        cached_results = await search_cache.get_async(cache_key)
        
        if cached_results:
            log(f"Cache hit for repository search: {query}", level="debug")
            return cached_results
        
        # Simulate a search operation
        log(f"Cache miss for repository search: {query}", level="debug")
        await asyncio.sleep(0.2)  # Simulate search latency
        
        # Filter repositories based on query
        results = []
        for repo in db.repositories.values():
            if query.lower() in repo["name"].lower():
                results.append(repo)
        
        # Cache with a shorter TTL for search results
        await search_cache.set_async(cache_key, results, ttl=300)  # 5 minutes
        
        return results

# Example function to demonstrate caching in action
async def demonstrate_caching():
    """Demonstrate caching features with example operations."""
    # Register warmup functions
    register_warmup_functions()
    
    # Start cache analytics
    await cache_analytics.start_monitoring(
        report_interval=10,  # 10 seconds for demo
        warmup_interval=30   # 30 seconds for demo
    )
    
    # Create repository service
    repo_service = RepositoryService()
    
    # First call - cache miss
    log("First call to get_repository - should be a cache miss", level="info")
    repo1 = await repo_service.get_repository(1)
    
    # Second call - cache hit
    log("Second call to get_repository - should be a cache hit", level="info")
    repo1_again = await repo_service.get_repository(1)
    
    # Search repositories - cache miss
    log("First call to search_repositories - should be a cache miss", level="info")
    search_results = await repo_service.search_repositories("Repository")
    
    # Search repositories again - cache hit
    log("Second call to search_repositories - should be a cache hit", level="info")
    search_results_again = await repo_service.search_repositories("Repository")
    
    # Wait to see some metrics
    log("Waiting to collect some cache metrics...", level="info")
    await asyncio.sleep(15)
    
    # Generate a report
    await cache_analytics.generate_performance_report()
    
    # Try manual warmup
    log("Manually warming up repository cache for IDs 2 and 3", level="info")
    await cache_analytics.warmup_cache("repository", ["2", "3"])
    
    # Verify warmup
    log("Verifying cache hit after manual warmup", level="info")
    repo2 = await repo_service.get_repository(2)
    
    # Stop monitoring
    await cache_analytics.stop_monitoring()
    
    log("Cache demonstration completed", level="info")

# Function to run the demo
def run_demo():
    """Run the caching demonstration."""
    asyncio.run(demonstrate_caching())

if __name__ == "__main__":
    run_demo() 