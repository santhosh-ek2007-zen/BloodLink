"""
app.py — Root-level entry point delegating to app/main.py.

Allows running either:
    python -m streamlit run app/main.py
or:
    python -m streamlit run app.py
"""

import runpy
from pathlib import Path

if __name__ in ("__main__", "streamlit"):
    main_file = Path(__file__).parent / "app" / "main.py"
    runpy.run_path(str(main_file), run_name="__main__")

