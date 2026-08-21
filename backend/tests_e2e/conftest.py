"""Fixtures partagées pour les tests E2E navigateur.

Démarre un serveur uvicorn dédié sur un port distinct (8766) avec une base SQLite
isolée (e2e_test.db), pour ne pas interférer avec la base de dev ni avec d'autres
tests pytest. Le serveur est démarré une fois par session ; la base est réinitialisée
au début de chaque module via le fixture `seed_db` (auto).
"""
import os
import socket
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

import pytest

E2E_PORT = 8766
E2E_DB = "e2e_test.db"
BASE_URL = f"http://127.0.0.1:{E2E_PORT}"
BACKEND_DIR = Path(__file__).resolve().parent.parent


def _port_libre(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _attendre_serveur(url: str, timeout_s: float = 30) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=2) as r:
                if r.status == 200:
                    return
        except (urllib.error.URLError, ConnectionResetError, TimeoutError):
            time.sleep(0.3)
    raise RuntimeError(f"Serveur E2E n'a pas démarré sur {url}")


@pytest.fixture(scope="session")
def live_server():
    """Démarre uvicorn sur le port 8766 avec base isolée, puis le tue à la fin."""
    if not _port_libre(E2E_PORT):
        raise RuntimeError(
            f"Port {E2E_PORT} déjà occupé — un précédent test E2E n'a pas été nettoyé."
        )

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{BACKEND_DIR / E2E_DB}"
    # Clé de chiffrement déterministe pour les tests
    env["APP_CRYPTO_KEY"] = "e2e-test-key-deterministe-1234567890"
    env["JWT_SECRET"] = "e2e-test-jwt-secret-deterministe-1234567890"

    # Reset DB avant de lancer
    (BACKEND_DIR / E2E_DB).unlink(missing_ok=True)

    # Seed (depuis le même env)
    subprocess.run(
        [sys.executable, "-m", "app.seed"],
        cwd=BACKEND_DIR, env=env, check=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", str(E2E_PORT),
         "--log-level", "warning"],
        cwd=BACKEND_DIR, env=env,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    try:
        _attendre_serveur(BASE_URL, timeout_s=30)
    except Exception:
        proc.terminate()
        out, err = proc.communicate(timeout=5)
        raise RuntimeError(f"Échec démarrage serveur E2E :\n{err.decode(errors='replace')}")

    yield BASE_URL

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    (BACKEND_DIR / E2E_DB).unlink(missing_ok=True)


@pytest.fixture
def page(page, live_server):
    """Override le fixture `page` standard pour pré-naviguer vers la base URL."""
    page.set_default_timeout(8000)
    return page


def _se_connecter(page, base_url: str, username: str, password: str) -> None:
    page.goto(f"{base_url}/login.html")
    page.fill('input[name="username"]', username)
    page.fill('input[name="password"]', password)
    page.click('button[type="submit"]')
    # On attend la redirection vers le dashboard
    page.wait_for_url(f"{base_url}/", timeout=10000)


@pytest.fixture
def admin_page(page, live_server):
    _se_connecter(page, live_server, "admin", "admin123")
    return page


@pytest.fixture
def agent_page(page, live_server):
    _se_connecter(page, live_server, "agent", "agent123")
    return page
