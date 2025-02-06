from neo4j import GraphDatabase
from config import config

driver = GraphDatabase.driver(
    config['neo4j']['uri'],
    auth=(config['neo4j']['user'], config['neo4j']['password'])
)

def run_query(cypher, params=None):
    session = driver.session()
    try:
        result = session.run(cypher, params or {})
        return [record.data() for record in result]
    finally:
        session.close()