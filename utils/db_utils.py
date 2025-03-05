import sys
import os

# Insert the project root into sys.path so that modules can be found.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import logging
import asyncio
from utils.logger import log, logger
from db.psql import query
from db.schema import create_all_tables
from db.neo4j_ops import run_query  # Import the Neo4j query function
from utils.error_handling import handle_async_errors, AsyncErrorBoundary

# Create the argument parser at module level
parser = argparse.ArgumentParser(
    description="Database utilities for cleaning and reinitializing PostgreSQL and Neo4j."
)
parser.add_argument("--clean", action="store_true",
                    help="Clean and reinitialize both PostgreSQL and Neo4j databases.")
parser.add_argument("--clean-postgres", action="store_true",
                    help="Clean and reinitialize only PostgreSQL database.")
parser.add_argument("--clean-neo4j", action="store_true",
                    help="Clean and reinitialize only Neo4j database.")
parser.add_argument("--debug", action="store_true",
                    help="Enable debug logging.")

def setup_logging(debug=False):
    # Get the Neo4j logger and set it to use our logger's handler
    neo4j_logger = logging.getLogger("neo4j")
    neo4j_logger.handlers = logger.handlers
    
    # Set level based on debug flag
    if not debug:
        neo4j_logger.setLevel(logging.INFO)
    # If debug is True, it will use the default level from our logger.py

@handle_async_errors
async def clean_postgresql():
    """Clean PostgreSQL database."""
    log("Cleaning PostgreSQL database...", level="info")
    async with AsyncErrorBoundary("cleaning postgresql"):
        try:
            # Drop the public schema and all its objects.
            task = asyncio.create_task(query("DROP SCHEMA public CASCADE;"))
            await task
            # Recreate the public schema.
            task = asyncio.create_task(query("CREATE SCHEMA public;"))
            await task
            # Reinitialize the tables and extensions.
            await create_all_tables()
            log("PostgreSQL cleaned and reinitialized.", level="info")
            return True
        except Exception as e:
            log(f"Error cleaning PostgreSQL: {e}", level="error")
            return False

@handle_async_errors
async def clean_neo4j():
    """Clean Neo4j database."""
    log("Cleaning Neo4j database...", level="info")
    async with AsyncErrorBoundary("cleaning neo4j"):
        try:
            # Use the Neo4j driver to clean the database
            task = asyncio.create_task(run_query("MATCH (n) DETACH DELETE n"))
            await task
            log("Neo4j cleaned.", level="info")
            return True
        except Exception as e:
            log(f"Error cleaning Neo4j: {e}", level="error")
            if "Connection refused" in str(e):
                log("Neo4j database connection failed. Make sure Neo4j is running.", level="error")
            return False

async def main_async(args):
    """Async main function."""
    # Set up logging based on debug flag
    setup_logging(args.debug)

    # If no specific clean option is selected but --clean is used, clean both
    if args.clean:
        success_pg = await clean_postgresql()
        success_neo = await clean_neo4j()
        if not (success_pg and success_neo):
            sys.exit(1)
    elif args.clean_postgres:
        if not await clean_postgresql():
            sys.exit(1)
    elif args.clean_neo4j:
        if not await clean_neo4j():
            sys.exit(1)
    else:
        parser.print_help()

def main():
    """Main entry point."""
    args = parser.parse_args()

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main_async(args))
    except KeyboardInterrupt:
        log("Database cleaning interrupted by user", level="info")
    except Exception as e:
        log(f"Error during database cleaning: {e}", level="error")
        sys.exit(1)

if __name__ == "__main__":
    main() 