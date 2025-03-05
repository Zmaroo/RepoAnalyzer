"""Configuration management with error handling."""

import os
import asyncio
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, AsyncErrorBoundary, ErrorSeverity
from parsers.models import FileType, FileClassification
import json

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

class Config:
    """Configuration management for the application."""
    
    def __init__(self):
        """Initialize configuration."""
        self._config = {}
        self._ai_config = {
            "deep_learning": {
                "enabled": True,
                "min_repositories": 2,
                "max_repositories": 10,
                "pattern_confidence_threshold": 0.7,
                "similarity_threshold": 0.8,
                "cache_ttl": 3600,  # 1 hour
                "max_patterns_per_repo": 1000,
                "max_patterns_total": 10000
            },
            "pattern_learning": {
                "enabled": True,
                "min_pattern_confidence": 0.6,
                "max_patterns_per_type": 100,
                "cache_ttl": 1800,  # 30 minutes
                "apply_automatically": False,
                "require_approval": True
            },
            "pattern_processing": {
                "enabled": True,
                "max_concurrent_tasks": 5,
                "timeout_seconds": 300,
                "retry_attempts": 3,
                "retry_delay": 5
            },
            "model_selection": {
                "default_model": "gpt-4",
                "fallback_model": "gpt-3.5-turbo",
                "embedding_model": "text-embedding-ada-002",
                "max_tokens": 4000,
                "temperature": 0.7
            },
            "pattern_storage": {
                "use_neo4j": True,
                "use_postgres": True,
                "max_pattern_size": 1000000,  # 1MB
                "compression_enabled": True
            },
            "pattern_validation": {
                "enabled": True,
                "validate_syntax": True,
                "validate_dependencies": True,
                "validate_compatibility": True,
                "max_validation_time": 60  # seconds
            },
            "pattern_metrics": {
                "track_complexity": True,
                "track_maintainability": True,
                "track_reusability": True,
                "track_usage": True,
                "metrics_update_interval": 3600  # 1 hour
            }
        }
        self._load_config()
    
    def _load_config(self):
        """Load configuration from environment and files."""
        # Load base configuration
        self._config.update({
            "database": {
                "host": os.getenv("DB_HOST", "localhost"),
                "port": int(os.getenv("DB_PORT", "5432")),
                "name": os.getenv("DB_NAME", "repo_analyzer"),
                "user": os.getenv("DB_USER", "postgres"),
                "password": os.getenv("DB_PASSWORD", ""),
                "pool_size": int(os.getenv("DB_POOL_SIZE", "5")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "10"))
            },
            "neo4j": {
                "uri": os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                "user": os.getenv("NEO4J_USER", "neo4j"),
                "password": os.getenv("NEO4J_PASSWORD", ""),
                "max_connections": int(os.getenv("NEO4J_MAX_CONNECTIONS", "50"))
            },
            "cache": {
                "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379"),
                "ttl": int(os.getenv("CACHE_TTL", "3600")),
                "max_size": int(os.getenv("CACHE_MAX_SIZE", "1000"))
            },
            "logging": {
                "level": os.getenv("LOG_LEVEL", "INFO"),
                "file": os.getenv("LOG_FILE", "repo_analyzer.log"),
                "max_size": int(os.getenv("LOG_MAX_SIZE", "10485760")),  # 10MB
                "backup_count": int(os.getenv("LOG_BACKUP_COUNT", "5"))
            }
        })
        
        # Load AI configuration
        self._config["ai"] = self._ai_config
        
        # Load from config file if exists
        config_file = os.getenv("CONFIG_FILE", "config.json")
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                file_config = json.load(f)
                self._deep_update(self._config, file_config)
    
    def _deep_update(self, d: Dict, u: Dict):
        """Recursively update dictionary."""
        for k, v in u.items():
            if isinstance(v, dict):
                d[k] = self._deep_update(d.get(k, {}), v)
            else:
                d[k] = v
        return d
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        keys = key.split('.')
        value = self._config
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k, default)
            else:
                return default
        
        return value
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI-specific configuration."""
        return self._config.get("ai", self._ai_config)
    
    def get_deep_learning_config(self) -> Dict[str, Any]:
        """Get deep learning configuration."""
        return self._config.get("ai", {}).get("deep_learning", self._ai_config["deep_learning"])
    
    def get_pattern_learning_config(self) -> Dict[str, Any]:
        """Get pattern learning configuration."""
        return self._config.get("ai", {}).get("pattern_learning", self._ai_config["pattern_learning"])
    
    def get_pattern_processing_config(self) -> Dict[str, Any]:
        """Get pattern processing configuration."""
        return self._config.get("ai", {}).get("pattern_processing", self._ai_config["pattern_processing"])
    
    def get_model_selection_config(self) -> Dict[str, Any]:
        """Get model selection configuration."""
        return self._config.get("ai", {}).get("model_selection", self._ai_config["model_selection"])
    
    def get_pattern_storage_config(self) -> Dict[str, Any]:
        """Get pattern storage configuration."""
        return self._config.get("ai", {}).get("pattern_storage", self._ai_config["pattern_storage"])
    
    def get_pattern_validation_config(self) -> Dict[str, Any]:
        """Get pattern validation configuration."""
        return self._config.get("ai", {}).get("pattern_validation", self._ai_config["pattern_validation"])
    
    def get_pattern_metrics_config(self) -> Dict[str, Any]:
        """Get pattern metrics configuration."""
        return self._config.get("ai", {}).get("pattern_metrics", self._ai_config["pattern_metrics"])
    
    def update_ai_config(self, new_config: Dict[str, Any]):
        """Update AI configuration."""
        self._deep_update(self._ai_config, new_config)
        self._config["ai"] = self._ai_config
    
    def update_deep_learning_config(self, new_config: Dict[str, Any]):
        """Update deep learning configuration."""
        self._deep_update(self._ai_config["deep_learning"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_pattern_learning_config(self, new_config: Dict[str, Any]):
        """Update pattern learning configuration."""
        self._deep_update(self._ai_config["pattern_learning"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_pattern_processing_config(self, new_config: Dict[str, Any]):
        """Update pattern processing configuration."""
        self._deep_update(self._ai_config["pattern_processing"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_model_selection_config(self, new_config: Dict[str, Any]):
        """Update model selection configuration."""
        self._deep_update(self._ai_config["model_selection"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_pattern_storage_config(self, new_config: Dict[str, Any]):
        """Update pattern storage configuration."""
        self._deep_update(self._ai_config["pattern_storage"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_pattern_validation_config(self, new_config: Dict[str, Any]):
        """Update pattern validation configuration."""
        self._deep_update(self._ai_config["pattern_validation"], new_config)
        self._config["ai"] = self._ai_config
    
    def update_pattern_metrics_config(self, new_config: Dict[str, Any]):
        """Update pattern metrics configuration."""
        self._deep_update(self._ai_config["pattern_metrics"], new_config)
        self._config["ai"] = self._ai_config
    
    def save_config(self, config_file: str = "config.json"):
        """Save configuration to file."""
        with open(config_file, 'w') as f:
            json.dump(self._config, f, indent=2)

# Create global instance
config = Config()

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