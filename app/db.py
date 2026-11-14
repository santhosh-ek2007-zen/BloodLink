import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_APP_DIR = Path(__file__).resolve().parent

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def _load_db_config() -> dict:
    secrets_path = PROJECT_ROOT / ".streamlit" / "secrets.toml"
    if secrets_path.exists():
        try:
            try:
                import tomllib
            except ImportError:
                import tomli as tomllib  # type: ignore
            with open(secrets_path, "rb") as f:
                data = tomllib.load(f)
            if "database" in data:
                return data["database"]
        except Exception:
            pass

    try:
        import streamlit as st
        if "database" in st.secrets:
            return st.secrets["database"]
    except Exception:
        pass

    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", 5432)),
        "dbname": os.getenv("DB_NAME", "neondb"),
        "user": os.getenv("DB_USER", "postgres"),
        "password": os.getenv("DB_PASSWORD", ""),
        "sslmode": os.getenv("DB_SSLMODE", "prefer"),
        "channel_binding": os.getenv("DB_CHANNEL_BINDING", "prefer"),
    }


def get_connection() -> psycopg.Connection:
    db_config = _load_db_config()
    kwargs = {
        "host": db_config["host"],
        "port": int(db_config.get("port", 5432)),
        "dbname": db_config["dbname"],
        "user": db_config["user"],
        "password": db_config["password"],
    }
    if "sslmode" in db_config:
        kwargs["sslmode"] = db_config["sslmode"]
    if "channel_binding" in db_config:
        kwargs["channel_binding"] = db_config["channel_binding"]

    return psycopg.connect(**kwargs)