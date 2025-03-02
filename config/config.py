"""Configuration management with error handling."""
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv
from utils.logger import log
from utils.error_handling import handle_errors, ProcessingError, ErrorBoundary, AsyncErrorBoundary
from parsers.models import FileType, FileClassification
load_dotenv()


@dataclass
class PostgresConfig:
    """PostgreSQL configuration."""
    host: str = os.getenv('PGHOST', 'localhost')
    port: int = int(os.getenv('PGPORT', '5432'))
    database: str = os.getenv('PGDATABASE', 'ra')
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
    """
    Parser configuration.
    Specify the location of language data and other parser-related settings.
    """
    language_data_path: str = os.getenv('LANGUAGE_DATA_PATH', './languages')


@dataclass
class RedisConfig:
    """Redis configuration."""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    db: int = int(os.getenv('REDIS_DB', '0'))
    password: str = os.getenv('REDIS_PASSWORD', None)


@dataclass
class FileConfig:
    """Configuration for file operations."""
    ignore_patterns: list = field(default_factory=lambda : ['*.tmp', '*.log'])

    @classmethod
@handle_errors(error_types=(Exception,))
    def create(cls):
        return cls()


postgres_config = PostgresConfig()
neo4j_config = Neo4jConfig()
parser_config = ParserConfig()
redis_config = RedisConfig()
file_config = FileConfig.create()


@handle_errors(error_types=ProcessingError)
def validate_configs() ->bool:
    """Validate all configuration settings."""
    with ErrorBoundary(operation_name='configuration validation'):
        if not all([postgres_config.host, postgres_config.user,
            postgres_config.database]):
            log('Invalid PostgreSQL configuration', level='error')
            return False
        if not all([neo4j_config.uri, neo4j_config.user, neo4j_config.password]
            ):
            log('Invalid Neo4j configuration', level='error')
            return False
        if not os.path.exists(parser_config.language_data_path):
            log('Invalid parser language data path', level='error')
            return False
        return True
