import os
import sys
from pathlib import Path

import psycopg
import streamlit as st
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

_APP_DIR = Path(__file__).resolve().parent

if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))


def get_connection() -> psycopg.Connection:

    try:
        db_config = st.secrets["database"]
    except Exception:
        db_config = {}

    return psycopg.connect(
        host=db_config.get("host") or os.getenv("DB_HOST", "localhost"),
        port=int(db_config.get("port") or os.getenv("DB_PORT", "5432")),
        dbname=db_config.get("dbname") or os.getenv("DB_NAME", "bloodlink"),
        user=db_config.get("user") or os.getenv("DB_USER", "postgres"),
        password=db_config.get("password") or os.getenv("DB_PASSWORD"),
        sslmode=db_config.get("sslmode") or os.getenv("DB_SSLMODE", "require")
    )