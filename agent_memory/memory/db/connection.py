# SQLite connection manager for the shared memory layer.


import os
import sqlite3

from agent_memory.memory.db.schema import init_db

DEFAULT_DB_PATH: str = os.environ.get("AGENT_MEMORY_DB_PATH", "memory.db")


# Returns a sqlite3 connection with row_factory = sqlite3.Row so rows are accessible by column name. Enables WAL mode for concurrent reads.
# Does NOT call init_db — caller is responsible.
def get_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


# Use for tests and CLI entrypoint
def get_initialized_connection(db_path: str = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    init_db(conn)
    return conn