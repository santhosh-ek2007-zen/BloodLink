"""
db.py — Root-level proxy to app/db.py.

Ensures that `from db import get_connection` succeeds regardless of whether
the working directory is the project root or the app/ directory.
"""

from app.db import get_connection

__all__ = ["get_connection"]

