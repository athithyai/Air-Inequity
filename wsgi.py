"""WSGI entry point for Gunicorn / Render deployment."""

import sys
from pathlib import Path

# Make the dashboard package importable from the repo root
sys.path.insert(0, str(Path(__file__).parent / "dashboard"))

from app import server  # noqa: F401  — Gunicorn binds to this
