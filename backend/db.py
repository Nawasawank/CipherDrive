import os
import psycopg2
from dotenv import load_dotenv
from contextlib import contextmanager

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

@contextmanager
def get_db():
    conn = psycopg2.connect(DATABASE_URL)
    try:
        yield conn
    finally:
        conn.close()
