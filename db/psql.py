import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import pool
from config import config

# Create a thread-safe connection pool
DB_POOL = pool.ThreadedConnectionPool(
    minconn=1,
    maxconn=10,
    host=config['postgres']['host'],
    user=config['postgres']['user'],
    password=config['postgres']['password'],
    database=config['postgres']['database'],
    port=config['postgres']['port']
)

def get_connection():
    return DB_POOL.getconn()

def release_connection(conn):
    DB_POOL.putconn(conn)

def query(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchall() if cur.description else None
            conn.commit()
            return result
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        release_connection(conn)