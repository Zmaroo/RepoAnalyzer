"""Database transaction coordination."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional
from utils.logger import log
from db.psql import _pool
from db.neo4j_ops import driver
from db.cache import cache

class TransactionCoordinator:
    """Coordinates transactions across different databases and caches."""
    
    def __init__(self):
        self.pg_conn = None
        self.neo4j_session = None
        self._lock = asyncio.Lock()
        
    async def _start_postgres(self):
        """Start PostgreSQL transaction."""
        if not self.pg_conn:
            self.pg_conn = await _pool.acquire()
            self.pg_transaction = self.pg_conn.transaction()
            await self.pg_transaction.start()
            
    async def _start_neo4j(self):
        """Start Neo4j transaction."""
        if not self.neo4j_session:
            self.neo4j_session = driver.session()
            self.neo4j_transaction = self.neo4j_session.begin_transaction()
    
    async def _commit_all(self):
        """Commit all active transactions."""
        try:
            if self.pg_conn:
                await self.pg_transaction.commit()
                
            if self.neo4j_session:
                await self.neo4j_transaction.commit()
                
        except Exception as e:
            log(f"Error committing transactions: {e}", level="error")
            await self._rollback_all()
            raise
            
    async def _rollback_all(self):
        """Rollback all active transactions."""
        try:
            if self.pg_conn:
                await self.pg_transaction.rollback()
                
            if self.neo4j_session:
                await self.neo4j_transaction.rollback()
                
        except Exception as e:
            log(f"Error rolling back transactions: {e}", level="error")
            raise
            
    async def _cleanup(self):
        """Clean up all resources."""
        try:
            if self.pg_conn:
                await _pool.release(self.pg_conn)
                self.pg_conn = None
                
            if self.neo4j_session:
                self.neo4j_session.close()
                self.neo4j_session = None
                
        except Exception as e:
            log(f"Error cleaning up transactions: {e}", level="error")
            raise

@asynccontextmanager
async def transaction_scope(invalidate_cache: bool = True):
    """
    Context manager for coordinated transactions.
    
    Usage:
    async with transaction_scope() as coordinator:
        # Perform database operations
        # Transactions will be automatically committed or rolled back
    """
    coordinator = TransactionCoordinator()
    try:
        async with coordinator._lock:
            await coordinator._start_postgres()
            await coordinator._start_neo4j()
            yield coordinator
            await coordinator._commit_all()
            if invalidate_cache:
                cache.clear()
    except Exception as e:
        await coordinator._rollback_all()
        raise
    finally:
        await coordinator._cleanup() 