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
    db_config = st.secrets["database"]
    st.write("Database host:", db_config["host"])
    st.write("Database name:", db_config["dbname"])
    return psycopg.connect(
        host=db_config["host"],
        port=int(db_config.get("port", 5432)),
        dbname=db_config["dbname"],
        user=db_config["user"],
        password=db_config["password"],
        sslmode=db_config.get("sslmode", "require"),
        channel_binding=db_config.get("channel_binding", "require")
    )