"""Application initialization and lifecycle management."""

import asyncio
import atexit
import os
import sys
from typing import Callable, List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum, auto

from utils.logger import log, logger
from utils.async_runner import cleanup_tasks, submit_async_task, get_loop
from utils.cache import cache_coordinator
from utils.cache_analytics import start_cache_analytics
from utils.shutdown import execute_shutdown_handlers
from utils.error_handling import AsyncErrorBoundary, ProcessingError, ErrorSeverity, ErrorAudit
from utils.health_monitor import global_health_monitor, ComponentStatus
from db.connection import connection_manager
from db.neo4j_ops import create_schema_indexes_and_constraints, get_neo4j_tools
from db.transaction import get_transaction_coordinator, initialize_transaction_coordinator

class InitStage(Enum):
    """Initialization stages in order of dependency."""
    LOGGING = auto()
    ERROR_HANDLING = auto()
    CACHE = auto()
    DATABASE = auto()
    PARSERS = auto()
    INDEXER = auto()
    AI_TOOLS = auto()
    WATCHER = auto()

@dataclass
class ComponentDependencies:
    """Component initialization dependencies."""
    stage: InitStage
    requires: List[InitStage]
    initialize: Callable
    initialized: bool = False

async def _initialize_components():
    """Initialize all application components asynchronously with dependency management."""
    try:
        # Define component dependencies and initialization order
        dependencies: Dict[str, ComponentDependencies] = {
            "logging": ComponentDependencies(
                stage=InitStage.LOGGING,
                requires=[],
                initialize=lambda: logger._initialize_logger()
            ),
            "error_handling": ComponentDependencies(
                stage=InitStage.ERROR_HANDLING,
                requires=[InitStage.LOGGING],
                initialize=lambda: ErrorAudit.analyze_codebase(os.getcwd())
            ),
            "cache": ComponentDependencies(
                stage=InitStage.CACHE,
                requires=[InitStage.LOGGING, InitStage.ERROR_HANDLING],
                initialize=lambda: cache_coordinator.initialize()
            ),
            "database": ComponentDependencies(
                stage=InitStage.DATABASE,
                requires=[InitStage.CACHE],
                initialize=_initialize_database_components
            ),
            "parsers": ComponentDependencies(
                stage=InitStage.PARSERS,
                requires=[InitStage.DATABASE],
                initialize=_initialize_parser_components
            ),
            "indexer": ComponentDependencies(
                stage=InitStage.INDEXER,
                requires=[InitStage.PARSERS],
                initialize=_initialize_indexer_components
            ),
            "ai_tools": ComponentDependencies(
                stage=InitStage.AI_TOOLS,
                requires=[InitStage.PARSERS, InitStage.INDEXER],
                initialize=_initialize_ai_components
            ),
            "watcher": ComponentDependencies(
                stage=InitStage.WATCHER,
                requires=[InitStage.INDEXER],
                initialize=_initialize_watcher_components
            )
        }

        # Initialize components in dependency order
        for component_name, component in dependencies.items():
            try:
                # Check if all required components are initialized
                for required_stage in component.requires:
                    required_components = [c for c in dependencies.values() if c.stage == required_stage]
                    if not all(c.initialized for c in required_components):
                        raise ProcessingError(f"Required stage {required_stage} not initialized for {component_name}")

                # Initialize component
                await global_health_monitor.update_component_status(
                    component_name,
                    ComponentStatus.INITIALIZING,
                    details={"stage": "starting"}
                )

                async with AsyncErrorBoundary(
                    operation_name=f"{component_name}_initialization",
                    error_types=ProcessingError,
                    severity=ErrorSeverity.CRITICAL
                ):
                    await component.initialize()
                    component.initialized = True
                    await log(f"{component_name} initialized", level="info")

                await global_health_monitor.update_component_status(
                    component_name,
                    ComponentStatus.HEALTHY,
                    details={"stage": "complete"}
                )

            except Exception as e:
                await log(f"Error initializing {component_name}: {e}", level="error")
                await global_health_monitor.update_component_status(
                    component_name,
                    ComponentStatus.UNHEALTHY,
                    error=True,
                    details={"initialization_error": str(e)}
                )
                raise ProcessingError(f"Failed to initialize {component_name}: {e}")

        # Start cache analytics after all components are initialized
        await start_cache_analytics()
        return True

    except Exception as e:
        await log(f"Error during component initialization: {e}", level="error")
        await global_health_monitor.update_component_status(
            "app_initialization",
            ComponentStatus.UNHEALTHY,
            error=True,
            details={"initialization_error": str(e)}
        )
        return False

async def _initialize_database_components():
    """Initialize database components in proper order."""
    # Initialize connection manager first
    await connection_manager.initialize()
    
    # Initialize transaction coordinator
    await initialize_transaction_coordinator()
    
    # Initialize PostgreSQL operations
    from db.psql import initialize as init_psql
    await init_psql()
    
    # Initialize Neo4j tools and schema
    neo4j_tools = await get_neo4j_tools()
    await create_schema_indexes_and_constraints()

async def _initialize_parser_components():
    """Initialize parser components."""
    from parsers import initialize_parser_system
    await initialize_parser_system()

async def _initialize_indexer_components():
    """Initialize indexer components."""
    from indexer.unified_indexer import UnifiedIndexer
    await UnifiedIndexer.create()

async def _initialize_ai_components():
    """Initialize AI components."""
    from ai_tools.ai_interface import AIAssistant
    await AIAssistant.create()

async def _initialize_watcher_components():
    """Initialize file watcher components."""
    from watcher.file_watcher import DirectoryWatcher
    await DirectoryWatcher.create()

async def initialize_application():
    """Initialize the application and all its components."""
    try:
        log("Initializing application...", level="info")
        
        # Register the cleanup handler
        atexit.register(lambda: asyncio.run(execute_shutdown_handlers()))
        
        # Initialize components
        await _initialize_components()
        
        log("Application initialized successfully", level="info")
        return True
    except Exception as e:
        log(f"Application initialization failed: {e}", level="error")
        return False

if __name__ == "__main__":
    # Use get_loop from async_runner instead of creating a new one
    loop = get_loop()
    try:
        success = loop.run_until_complete(initialize_application())
        if not success:
            sys.exit(1)
    except RuntimeError as e:
        if "This event loop is already running" in str(e):
            # If the loop is already running, use submit_async_task
            future = submit_async_task(initialize_application())
            success = loop.run_until_complete(asyncio.wrap_future(future))
            if not success:
                sys.exit(1) 