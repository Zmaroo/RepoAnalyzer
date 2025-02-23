"""Database connection management."""

from neo4j import GraphDatabase
from config import neo4j_config

# Create the Neo4j driver instance
driver = GraphDatabase.driver(
    neo4j_config.uri,
    auth=(neo4j_config.user, neo4j_config.password)
) 