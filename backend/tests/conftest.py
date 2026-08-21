"""Fixtures pytest — base SQLite en mémoire, isolée pour chaque test."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app import models
from app.services import auth as auth_service


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = SessionTesting()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def _seed_users(db_engine):
    """Crée 2 équipes + un admin + un agent dans la base du test."""
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    s = SessionTesting()
    try:
        eq_front = models.Equipe(code="FRONT", libelle="Front-office")
        eq_back = models.Equipe(code="BACK", libelle="Back-office")
        s.add_all([eq_front, eq_back])
        s.flush()
        admin = models.Agent(
            nom="Admin", prenom="Test", email_pro="admin@test.ci",
            role="ADMIN", username="admin", id_equipe=eq_back.id,
            password_hash=auth_service.hasher_mot_de_passe("admin123"),
        )
        agent = models.Agent(
            nom="Agent", prenom="Test", email_pro="agent@test.ci",
            role="AGENT", username="agent", id_equipe=eq_front.id,
            password_hash=auth_service.hasher_mot_de_passe("agent123"),
        )
        s.add_all([admin, agent])
        s.commit()
    finally:
        s.close()


def _make_client(db_engine) -> TestClient:
    """Crée un TestClient avec dependency_override sur get_db."""
    SessionTesting = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override():
        s = SessionTesting()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override
    return TestClient(app)


@pytest.fixture
def anon_client(db_engine, _seed_users):
    """Client HTTP non authentifié — utile pour tester les 401/403."""
    yield _make_client(db_engine)
    app.dependency_overrides.clear()


def _login(test_client: TestClient, username: str, password: str) -> str:
    r = test_client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def client(db_engine, _seed_users):
    """Client HTTP pré-authentifié en ADMIN — utilisé par la plupart des tests.

    Sa propre instance (pas anon_client) pour pouvoir être utilisé dans le même
    test qu'agent_client sans conflit de headers.
    """
    c = _make_client(db_engine)
    token = _login(c, "admin", "admin123")
    c.headers["Authorization"] = f"Bearer {token}"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def agent_client(db_engine, _seed_users):
    """Client HTTP pré-authentifié en AGENT — utilisé pour tests RBAC.

    Instance distincte du fixture `client` (cf. docstring de `client`).
    """
    c = _make_client(db_engine)
    token = _login(c, "agent", "agent123")
    c.headers["Authorization"] = f"Bearer {token}"
    yield c
    app.dependency_overrides.clear()


@pytest.fixture
def payload_minimal():
    return {
        "canal": "EMAIL",
        "categorie": "FINANCIERE",
        "sous_categorie": "Débit non autorisé",
        "priorite": "STANDARD",
        "description": "Description suffisamment longue pour passer la validation.",
        "montant_enjeu": 0,
        "client": {
            "nom": "Test", "prenom": "Cas",
            "email": "test@example.ci", "telephone": "+225 00 00 00 00 00",
        },
    }
