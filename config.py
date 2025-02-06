import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

config = {
    'postgres': {
        'host': os.getenv('PGHOST'),
        'user': os.getenv('PGUSER'),
        'password': os.getenv('PGPASSWORD'),
        'database': os.getenv('PGDATABASE'),
        'port': os.getenv('PGPORT'),
    },
    'neo4j': {
        'uri': os.getenv('NEO4J_URI'),
        'user': os.getenv('NEO4J_USER'),
        'password': os.getenv('NEO4J_PASSWORD'),
    }
}