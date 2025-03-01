#!/usr/bin/env python3
"""
Cache warming utility for the RepoAnalyzer project.

This module extends the existing caching architecture with specialized
warming capabilities, focusing on pattern warming and proactive caching
strategies to improve system performance.
"""

import os
import sys
import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable, Awaitable, Set
from datetime import datetime
import traceback

from utils.logger import log
from utils.error_handling import handle_async_errors, ErrorBoundary
from utils.cache import (
    UnifiedCache, cache_coordinator, pattern_cache,
    repository_cache, search_cache, embedding_cache,
    parser_cache, graph_cache, ast_cache
)
from utils.cache_analytics import cache_analytics

# Import MemoryBoundedCache and PatternCache if available
try:
    from utils.memory_bounded_cache import MemoryBoundedCache, PatternCache
    MEMORY_BOUNDED_CACHE_AVAILABLE = True
except ImportError:
    MEMORY_BOUNDED_CACHE_AVAILABLE = False


class CacheWarmer:
    """
    Specialized cache warming utility that provides targeted warming strategies
    to optimize system performance.
    """
    
    def __init__(self):
        self._warmup_registry: Dict[str, Dict[str, Callable]] = {}
        self._warm_status: Dict[str, Dict[str, Any]] = {}
        self._is_running = False
        self._task = None
    
    def register_warmup_strategy(self, 
                                cache_name: str, 
                                strategy_name: str, 
                                warmup_func: Callable):
        """
        Register a warming strategy for a specific cache.
        
        Args:
            cache_name: Name of the cache to warm
            strategy_name: Name of the warming strategy
            warmup_func: Function that implements the warming strategy
        """
        if cache_name not in self._warmup_registry:
            self._warmup_registry[cache_name] = {}
            
        self._warmup_registry[cache_name][strategy_name] = warmup_func
        log(f"Registered warming strategy '{strategy_name}' for cache '{cache_name}'", 
            level="info")
    
    @handle_async_errors
    async def warm_cache(self, 
                        cache_name: str, 
                        strategy_name: str, 
                        **kwargs) -> bool:
        """
        Manually execute a specific warming strategy.
        
        Args:
            cache_name: Name of the cache to warm
            strategy_name: Name of the warming strategy to use
            **kwargs: Additional parameters for the warming strategy
            
        Returns:
            bool: True if successful, False otherwise
        """
        if cache_name not in self._warmup_registry:
            log(f"No warming strategies registered for cache '{cache_name}'", 
                level="error")
            return False
            
        if strategy_name not in self._warmup_registry[cache_name]:
            log(f"Warming strategy '{strategy_name}' not found for cache '{cache_name}'", 
                level="error")
            return False
            
        # Update warm status
        if cache_name not in self._warm_status:
            self._warm_status[cache_name] = {}
            
        self._warm_status[cache_name][strategy_name] = {
            "last_run": datetime.now().isoformat(),
            "status": "running"
        }
        
        # Execute warming strategy
        try:
            warmup_func = self._warmup_registry[cache_name][strategy_name]
            result = await warmup_func(**kwargs)
            
            # Update status
            self._warm_status[cache_name][strategy_name]["status"] = "success"
            log(f"Successfully executed warming strategy '{strategy_name}' for cache '{cache_name}'", 
                level="info")
            return True
            
        except Exception as e:
            # Update status
            self._warm_status[cache_name][strategy_name]["status"] = "failed"
            self._warm_status[cache_name][strategy_name]["error"] = str(e)
            log(f"Error executing warming strategy '{strategy_name}' for cache '{cache_name}': {e}", 
                level="error")
            traceback.print_exc()
            return False
    
    @handle_async_errors
    async def start_proactive_warming(self, interval: int = 3600):
        """
        Start proactive background cache warming.
        
        Args:
            interval: Time between warming cycles in seconds (default: 1 hour)
        """
        if self._is_running:
            log("Proactive cache warming is already running", level="warning")
            return
            
        self._is_running = True
        self._task = asyncio.create_task(self._proactive_warming_loop(interval))
        log("Started proactive cache warming", level="info")
    
    @handle_async_errors
    async def stop_proactive_warming(self):
        """Stop proactive background cache warming."""
        if not self._is_running:
            return
            
        self._is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            
        log("Stopped proactive cache warming", level="info")
    
    @handle_async_errors
    async def _proactive_warming_loop(self, interval: int):
        """
        Background loop for proactive cache warming.
        
        Args:
            interval: Time between warming cycles in seconds
        """
        try:
            while self._is_running:
                await self._execute_all_warming_strategies()
                
                # Sleep until next warming cycle
                await asyncio.sleep(interval)
                
        except asyncio.CancelledError:
            log("Proactive warming loop cancelled", level="info")
            raise
        except Exception as e:
            log(f"Error in proactive warming loop: {e}", level="error")
            self._is_running = False
    
    @handle_async_errors
    async def _execute_all_warming_strategies(self):
        """Execute all registered warming strategies."""
        log("Starting proactive cache warming cycle", level="info")
        
        for cache_name, strategies in self._warmup_registry.items():
            for strategy_name in strategies:
                with ErrorBoundary(f"executing warming strategy '{strategy_name}' for '{cache_name}'"):
                    await self.warm_cache(cache_name, strategy_name)
        
        log("Completed proactive cache warming cycle", level="info")
    
    def get_warming_status(self) -> Dict[str, Any]:
        """
        Get the status of all cache warming operations.
        
        Returns:
            Dict with cache warming status information
        """
        return self._warm_status


# ====================================================================
# Pattern-specific warming strategies
# ====================================================================

@handle_async_errors
async def warm_common_patterns(limit: int = 50, **kwargs) -> bool:
    """
    Warm the pattern cache with commonly used patterns.
    
    Args:
        limit: Maximum number of patterns to warm
        
    Returns:
        bool: True if successful
    """
    from utils.patterns import get_common_patterns
    
    with ErrorBoundary("warming common patterns"):
        # Get most commonly used patterns
        patterns = await get_common_patterns(limit)
        
        if not patterns:
            log("No common patterns found for warming", level="warning")
            return False
        
        # Use the existing cache warmup method
        await pattern_cache.warmup(patterns)
        
        log(f"Warmed pattern cache with {len(patterns)} common patterns", level="info")
        return True


@handle_async_errors
async def warm_language_specific_patterns(language: str, **kwargs) -> bool:
    """
    Warm the pattern cache with patterns specific to a programming language.
    
    Args:
        language: Programming language to warm patterns for
        
    Returns:
        bool: True if successful
    """
    from utils.patterns import get_language_patterns
    
    with ErrorBoundary(f"warming patterns for language {language}"):
        # Get patterns for the specific language
        patterns = await get_language_patterns(language)
        
        if not patterns:
            log(f"No patterns found for language '{language}'", level="warning")
            return False
        
        # Use the existing cache warmup method
        await pattern_cache.warmup(patterns)
        
        log(f"Warmed pattern cache with {len(patterns)} patterns for language '{language}'", 
            level="info")
        return True


@handle_async_errors
async def warm_by_complexity(min_complexity: float = 0.7, **kwargs) -> bool:
    """
    Warm patterns based on complexity to prioritize complex pattern compilation.
    
    Args:
        min_complexity: Minimum complexity threshold (0-1)
        
    Returns:
        bool: True if successful
    """
    from utils.patterns import get_pattern_complexity
    
    with ErrorBoundary("warming complex patterns"):
        # Get patterns with their complexity
        patterns_with_complexity = await get_pattern_complexity()
        
        # Filter by complexity threshold
        complex_patterns = {
            name: pattern 
            for name, (pattern, complexity) in patterns_with_complexity.items()
            if complexity >= min_complexity
        }
        
        if not complex_patterns:
            log(f"No patterns with complexity >= {min_complexity} found", level="warning")
            return False
        
        # Use the existing cache warmup method
        await pattern_cache.warmup(complex_patterns)
        
        log(f"Warmed pattern cache with {len(complex_patterns)} complex patterns", 
            level="info")
        return True


# ====================================================================
# Repository cache warming strategies
# ====================================================================

@handle_async_errors
async def warm_recent_repositories(limit: int = 10, **kwargs) -> bool:
    """
    Warm the repository cache with recently accessed repositories.
    
    Args:
        limit: Maximum number of repositories to warm
        
    Returns:
        bool: True if successful
    """
    from utils.repository import get_recent_repositories
    
    with ErrorBoundary("warming recent repositories"):
        # Get recently accessed repositories
        repositories = await get_recent_repositories(limit)
        
        if not repositories:
            log("No recent repositories found for warming", level="warning")
            return False
        
        # Use the existing cache warmup method
        await repository_cache.warmup(repositories)
        
        log(f"Warmed repository cache with {len(repositories)} recent repositories", 
            level="info")
        return True


# ====================================================================
# AST cache warming strategies
# ====================================================================

@handle_async_errors
async def warm_ast_for_common_files(limit: int = 20, **kwargs) -> bool:
    """
    Warm the AST cache with ASTs for commonly accessed files.
    
    Args:
        limit: Maximum number of files to warm
        
    Returns:
        bool: True if successful
    """
    from utils.ast_parser import parse_files_for_cache
    
    with ErrorBoundary("warming AST cache for common files"):
        # Get commonly accessed files
        from utils.file_access import get_commonly_accessed_files
        common_files = await get_commonly_accessed_files(limit)
        
        if not common_files:
            log("No common files found for AST warming", level="warning")
            return False
        
        # Parse ASTs for these files
        parsed_asts = await parse_files_for_cache(common_files)
        
        # Use the existing cache warmup method
        await ast_cache.warmup(parsed_asts)
        
        log(f"Warmed AST cache with {len(parsed_asts)} ASTs for common files", 
            level="info")
        return True


# Create global instance
cache_warmer = CacheWarmer()

# Register example warming strategies
cache_warmer.register_warmup_strategy("patterns", "common_patterns", warm_common_patterns)
cache_warmer.register_warmup_strategy("patterns", "language_specific", warm_language_specific_patterns)
cache_warmer.register_warmup_strategy("patterns", "complex_patterns", warm_by_complexity)
cache_warmer.register_warmup_strategy("repositories", "recent", warm_recent_repositories)
cache_warmer.register_warmup_strategy("ast", "common_files", warm_ast_for_common_files)

# Initialize function
def initialize_cache_warmer(auto_start: bool = False, interval: int = 3600):
    """
    Initialize the cache warmer.
    
    Args:
        auto_start: Whether to automatically start proactive warming
        interval: Time between warming cycles in seconds
    """
    if auto_start:
        asyncio.create_task(cache_warmer.start_proactive_warming(interval))
    return cache_warmer 