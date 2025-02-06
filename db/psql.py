import psycopg2
from psycopg2.extras import RealDictCursor
from config import config

def get_connection():
    conf = config['postgres']
    conn = psycopg2.connect(
        host=conf['host'],
        user=conf['user'],
        password=conf['password'],
        database=conf['database'],
        port=conf['port']
    )
    return conn

def query(sql, params=None):
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            result = cur.fetchall() if cur.description else None
            conn.commit()
            return result
    finally:
        conn.close()