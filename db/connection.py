"""Database connection management."""

from neo4j import GraphDatabase
from config import Neo4jConfig

# Create the Neo4j driver instance
driver = GraphDatabase.driver(
    Neo4jConfig.uri,
    auth=(Neo4jConfig.user, Neo4jConfig.password)
) 