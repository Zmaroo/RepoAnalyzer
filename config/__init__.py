"""Configuration package."""

from .config import (
    PostgresConfig,
    Neo4jConfig,
    ParserConfig,
    postgres_config,
    neo4j_config,
    parser_config
)

from typing import Dict, Any

# Parser configuration
parser_config: Dict[str, Any] = {
    "max_file_size": 1024 * 1024,  # 1MB
    "timeout": 30,  # seconds
    "cache_enabled": True
}

# Cache configuration
redis_config: Dict[str, Any] = {
    "host": "localhost",
    "port": 6379,
    "db": 0,
    "password": None,
    "socket_timeout": 5
}

# Neo4j configuration
neo4j_config: Dict[str, Any] = {
    "uri": "bolt://localhost:7687",
    "user": "neo4j",
    "password": "password"
}

# PostgreSQL configuration
postgres_config: Dict[str, Any] = {
    "host": "localhost",
    "port": 5432,
    "database": "repoanalyzer",
    "user": "postgres",
    "password": "password"
}

__all__ = [
    'PostgresConfig',
    'Neo4jConfig',
    'ParserConfig',
    'postgres_config',
    'neo4j_config',
    'parser_config'
] 