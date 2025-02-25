"""Configuration management with error handling."""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, ErrorBoundary
from parsers.models import FileType, FileClassification

# Load environment variables from a .env file
load_dotenv()

@dataclass
class PostgresConfig:
    """PostgreSQL configuration."""
    host: str = os.getenv('PGHOST', 'localhost')
    port: int = int(os.getenv('PGPORT', '5432'))
    database: str = os.getenv('PGDATABASE', 'repoanalyzer')
    user: str = os.getenv('PGUSER', 'postgres')
    password: str = os.getenv('PGPASSWORD', 'password')

@dataclass
class Neo4jConfig:
    """Neo4j configuration."""
    uri: str = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user: str = os.getenv('NEO4J_USER', 'neo4j')
    password: str = os.getenv('NEO4J_PASSWORD', 'password')
    database: str = os.getenv('NEO4J_DATABASE', 'neo4j')

@dataclass
class ParserConfig:
    """Parser configuration."""
    max_file_size: int = 1024 * 1024  # 1MB
    timeout: int = 30  # seconds
    cache_enabled: bool = True
    language_data_path: str = os.getenv('PARSER_LANGUAGE_DATA', 'parsers/data')

@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    db: int = int(os.getenv('REDIS_DB', '0'))
    password: str = os.getenv('REDIS_PASSWORD', None)

# New FileConfig class for file-related settings.
@dataclass
class FileConfig:
    """Configuration for file operations."""
    # List of file patterns to ignore.
    ignore_patterns: list = field(default_factory=lambda: ["*.tmp", "*.log"])

    @classmethod
    def create(cls):
        return cls()

# Create global configuration instances
postgres_config = PostgresConfig()
neo4j_config = Neo4jConfig()
parser_config = ParserConfig()
redis_config = RedisConfig()
file_config = FileConfig.create()  # Global FileConfig instance

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