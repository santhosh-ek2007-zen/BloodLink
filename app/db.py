"""
app/db.py — BloodLink database connection module.

Single source of truth for PostgreSQL connections.
Loads credentials from the .env file in the project root.
All other modules import get_connection() from here.
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

# Resolve project root regardless of the working directory the caller uses.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

# Add the app/ directory to sys.path so that sibling modules can import
# each other whether the app is launched from the project root or from app/.
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def get_connection() -> psycopg.Connection:
    """Open and return a psycopg 3 connection to the BloodLink database.

    The caller is responsible for closing the connection.
    Use as a context manager where possible::

        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(...)

    Returns
    -------
    psycopg.Connection
        An open database connection.

    Raises
    ------
    psycopg.OperationalError
        If the database is unreachable or credentials are wrong.
    """
    return psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        dbname=os.getenv("DB_NAME", "bloodlink"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )
