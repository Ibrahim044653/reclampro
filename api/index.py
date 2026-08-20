"""Point d'entrée Vercel — importe l'app FastAPI du backend."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.main import app  # noqa: F401 — Vercel cherche la variable 'app'
