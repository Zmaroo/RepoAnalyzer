"""Configuration management with error handling."""

import os
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, AsyncErrorBoundary, ErrorSeverity
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
    min_pool_size: int = int(os.getenv('PG_MIN_POOL_SIZE', '5'))
    max_pool_size: int = int(os.getenv('PG_MAX_POOL_SIZE', '20'))
    connection_timeout: float = float(os.getenv('PG_CONNECTION_TIMEOUT', '30.0'))
    max_retries: int = int(os.getenv('PG_MAX_RETRIES', '3'))
    retry_delay: float = float(os.getenv('PG_RETRY_DELAY', '1.0'))

@dataclass
class Neo4jConfig:
    """Neo4j configuration."""
    uri: str = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user: str = os.getenv('NEO4J_USER', 'neo4j')
    password: str = os.getenv('NEO4J_PASSWORD', 'password')
    database: str = os.getenv('NEO4J_DATABASE', 'neo4j')
    max_connection_lifetime: int = int(os.getenv('NEO4J_MAX_CONNECTION_LIFETIME', '3600'))
    max_connection_pool_size: int = int(os.getenv('NEO4J_MAX_POOL_SIZE', '50'))
    connection_timeout: float = float(os.getenv('NEO4J_CONNECTION_TIMEOUT', '30.0'))
    max_retries: int = int(os.getenv('NEO4J_MAX_RETRIES', '3'))
    retry_delay: float = float(os.getenv('NEO4J_RETRY_DELAY', '1.0'))

@dataclass
class ParserConfig:
    """
    Parser configuration.
    Specify the location of language data and other parser-related settings.
    """
    language_data_path: str = os.getenv("LANGUAGE_DATA_PATH", "./languages")
    max_file_size: int = int(os.getenv("MAX_FILE_SIZE", "1048576"))  # 1MB default
    supported_languages: List[str] = field(default_factory=lambda: [
        "python", "javascript", "typescript", "java", "go", "rust"
    ])
    parse_timeout: float = float(os.getenv("PARSE_TIMEOUT", "30.0"))
    batch_size: int = int(os.getenv("PARSER_BATCH_SIZE", "100"))

@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    db: int = int(os.getenv('REDIS_DB', '0'))
    password: str = os.getenv('REDIS_PASSWORD', None)
    max_connections: int = int(os.getenv('REDIS_MAX_CONNECTIONS', '10'))
    connection_timeout: float = float(os.getenv('REDIS_CONNECTION_TIMEOUT', '5.0'))

@dataclass
class DatabaseConfig:
    """Database-wide configuration settings."""
    transaction_timeout: float = float(os.getenv('DB_TRANSACTION_TIMEOUT', '30.0'))
    max_transaction_retries: int = int(os.getenv('DB_MAX_TRANSACTION_RETRIES', '3'))
    health_check_interval: int = int(os.getenv('DB_HEALTH_CHECK_INTERVAL', '60'))
    connection_check_interval: int = int(os.getenv('DB_CONNECTION_CHECK_INTERVAL', '300'))
    error_threshold: int = int(os.getenv('DB_ERROR_THRESHOLD', '5'))
    cleanup_interval: int = int(os.getenv('DB_CLEANUP_INTERVAL', '3600'))

@dataclass
class GraphConfig:
    """Graph database specific configuration."""
    projection_timeout: float = float(os.getenv('GRAPH_PROJECTION_TIMEOUT', '300.0'))
    max_nodes_per_projection: int = int(os.getenv('GRAPH_MAX_NODES', '1000000'))
    max_relationships_per_projection: int = int(os.getenv('GRAPH_MAX_RELATIONSHIPS', '5000000'))
    projection_memory_limit: str = os.getenv('GRAPH_MEMORY_LIMIT', '2G')
    algorithm_timeout: float = float(os.getenv('GRAPH_ALGORITHM_TIMEOUT', '600.0'))
    cache_ttl: int = int(os.getenv('GRAPH_CACHE_TTL', '3600'))
    sync_interval: int = int(os.getenv('GRAPH_SYNC_INTERVAL', '300'))

@dataclass
class FileConfig:
    """Configuration for file operations."""
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "*.tmp", "*.log", "*.pyc", "__pycache__", "node_modules",
        ".git", ".env", "*.swp", "*.swo"
    ])
    max_file_size: int = int(os.getenv('MAX_FILE_SIZE', '1048576'))  # 1MB
    chunk_size: int = int(os.getenv('FILE_CHUNK_SIZE', '8192'))
    supported_encodings: List[str] = field(default_factory=lambda: [
        'utf-8', 'latin-1', 'ascii', 'utf-16'
    ])
    
    @classmethod
    def create(cls):
        return cls()

@dataclass
class RetryConfig:
    """Configuration for retry mechanisms."""
    max_retries: int = int(os.getenv('MAX_RETRIES', '3'))
    base_delay: float = float(os.getenv('RETRY_BASE_DELAY', '1.0'))
    max_delay: float = float(os.getenv('RETRY_MAX_DELAY', '30.0'))
    jitter_factor: float = float(os.getenv('RETRY_JITTER', '0.1'))
    error_threshold: int = int(os.getenv('RETRY_ERROR_THRESHOLD', '5'))
    cooldown_period: int = int(os.getenv('RETRY_COOLDOWN', '300'))

# Create global configuration instances
postgres_config = PostgresConfig()
neo4j_config = Neo4jConfig()
parser_config = ParserConfig()
redis_config = RedisConfig()
file_config = FileConfig.create()
database_config = DatabaseConfig()
graph_config = GraphConfig()
retry_config = RetryConfig()

@handle_errors(error_types=(Exception,))
async def validate_configs() -> bool:
    """Validate all configuration settings."""
    async with AsyncErrorBoundary("configuration validation", severity=ErrorSeverity.CRITICAL):
        # Validate PostgreSQL config
        if not all([
            postgres_config.host,
            postgres_config.port,
            postgres_config.database,
            postgres_config.user,
            postgres_config.password
        ]):
            log("Invalid PostgreSQL configuration", level="error")
            return False

        # Validate Neo4j config
        if not all([
            neo4j_config.uri,
            neo4j_config.user,
            neo4j_config.password,
            neo4j_config.database
        ]):
            log("Invalid Neo4j configuration", level="error")
            return False

        # Validate parser config
        if not os.path.exists(parser_config.language_data_path):
            log("Language data path does not exist", level="error")
            return False

        return True 