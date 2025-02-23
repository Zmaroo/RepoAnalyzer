import sys
import os

# Insert the project root into sys.path so that modules can be found.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import argparse
import logging
from utils.logger import log, logger
from db.psql import query
from db.schema import create_all_tables
from db.neo4j_ops import run_query  # Import the Neo4j query function

def setup_logging(debug=False):
    # Get the Neo4j logger and set it to use our logger's handler
    neo4j_logger = logging.getLogger("neo4j")
    neo4j_logger.handlers = logger.handlers
    
    # Set level based on debug flag
    if not debug:
        neo4j_logger.setLevel(logging.INFO)
    # If debug is True, it will use the default level from our logger.py

def clean_postgresql():
    log("Cleaning PostgreSQL database...", level="info")
    try:
        # Drop the public schema and all its objects.
        query("DROP SCHEMA public CASCADE;")
        # Recreate the public schema.
        query("CREATE SCHEMA public;")
        # Reinitialize the tables and extensions.
        create_all_tables()
        log("PostgreSQL cleaned and reinitialized.", level="info")
        return True
    except Exception as e:
        log(f"Error cleaning PostgreSQL: {e}", level="error")
        return False

def clean_neo4j():
    log("Cleaning Neo4j database...", level="info")
    try:
        # Use the Neo4j driver to clean the database
        run_query("MATCH (n) DETACH DELETE n")
        log("Neo4j cleaned.", level="info")
        return True
    except Exception as e:
        log(f"Error cleaning Neo4j: {e}", level="error")
        if "Connection refused" in str(e):
            log("Neo4j database connection failed. Make sure Neo4j is running.", level="error")
        return False

def main():
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
    
    args = parser.parse_args()

    # Set up logging based on debug flag
    setup_logging(args.debug)

    # If no specific clean option is selected but --clean is used, clean both
    if args.clean:
        success_pg = clean_postgresql()
        success_neo = clean_neo4j()
        if not (success_pg and success_neo):
            exit(1)
    elif args.clean_postgres:
        if not clean_postgresql():
            exit(1)
    elif args.clean_neo4j:
        if not clean_neo4j():
            exit(1)
    else:
        parser.print_help()

if __name__ == "__main__":
    main() 