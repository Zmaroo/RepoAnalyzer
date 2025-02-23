"""Configuration management with error handling."""

import os
from dataclasses import dataclass
from dotenv import load_dotenv
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, ErrorBoundary
from parsers.models import FileType, FileClassification

# Load environment variables from a .env file
load_dotenv()

@dataclass
class PostgresConfig:
    host: str = os.getenv('PGHOST', 'localhost')
    user: str = os.getenv('PGUSER', 'user')
    password: str = os.getenv('PGPASSWORD', 'password')
    database: str = os.getenv('PGDATABASE', 'mydb')
    port: int = int(os.getenv('PGPORT', '5432'))

@dataclass
class Neo4jConfig:
    uri: str = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user: str = os.getenv('NEO4J_USER', 'neo4j')
    password: str = os.getenv('NEO4J_PASSWORD', 'password')
    database: str = os.getenv('NEO4J_DATABASE', 'neo4j')

@dataclass
class ParserConfig:
    language_data_path: str = os.getenv('PARSER_LANGUAGE_DATA', 'parsers/data')
    # Add additional parser-specific settings here if needed.

# Create global configuration objects to be imported elsewhere
postgres_config = PostgresConfig()
neo4j_config = Neo4jConfig()
parser_config = ParserConfig()

@handle_errors(error_types=ProcessingError)
def validate_configs() -> bool:
    """Validate all configuration settings."""
    with ErrorBoundary("configuration validation"):
        # Validate PostgreSQL config
        if not all([
            postgres_config.host,
            postgres_config.user,
            postgres_config.database
        ]):
            log("Invalid PostgreSQL configuration", level="error")
            return False
        
        # Validate Neo4j config
        if not all([
            neo4j_config.uri,
            neo4j_config.user,
            neo4j_config.password
        ]):
            log("Invalid Neo4j configuration", level="error")
            return False
        
        # Validate parser config
        if not os.path.exists(parser_config.language_data_path):
            log("Invalid parser language data path", level="error")
            return False
        
        return True 