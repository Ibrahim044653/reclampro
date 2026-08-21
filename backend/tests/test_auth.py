"""Tests d'authentification + RBAC (NFR004)."""


def test_login_admin_ok(anon_client):
    r = anon_client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    data = r.json()
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 50
    assert data["utilisateur"]["role"] == "ADMIN"


def test_login_agent_ok(anon_client):
    r = anon_client.post("/api/auth/login", json={"username": "agent", "password": "agent123"})
    assert r.status_code == 200
    assert r.json()["utilisateur"]["role"] == "AGENT"


def test_login_mauvais_mdp(anon_client):
    r = anon_client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_utilisateur_inconnu(anon_client):
    r = anon_client.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert r.status_code == 401


def test_routes_protegees_sans_token(anon_client):
    """Toute route hors /api/auth et /api/health refuse sans token."""
    assert anon_client.get("/api/dashboard").status_code == 401
    assert anon_client.get("/api/reclamations").status_code == 401
    assert anon_client.get("/api/agents").status_code == 401
    assert anon_client.get("/api/exports/registre.csv").status_code == 401


def test_health_reste_public(anon_client):
    assert anon_client.get("/api/health").status_code == 200


def test_endpoint_me(anon_client):
    token = anon_client.post(
        "/api/auth/login", json={"username": "admin", "password": "admin123"}
    ).json()["access_token"]
    r = anon_client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["username"] == "admin"


def test_token_invalide_refuse(anon_client):
    r = anon_client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.token"})
    assert r.status_code == 401


def test_agent_ne_peut_pas_exporter_registre(agent_client):
    """RBAC : export reservé aux ADMINs."""
    r = agent_client.get("/api/exports/registre.csv")
    assert r.status_code == 403


def test_admin_peut_exporter_registre(client):
    r = client.get("/api/exports/registre.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]


def test_agent_ne_peut_pas_cloturer(agent_client, payload_minimal):
    """RBAC : clôture réservée aux ADMINs (mais création autorisée)."""
    code = agent_client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        agent_client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    r = agent_client.post(f"/api/reclamations/{code}/cloture", json={"motif": "FAVORABLE"})
    assert r.status_code == 403


def test_agent_peut_creer_et_commenter(agent_client, payload_minimal):
    code = agent_client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = agent_client.post(f"/api/reclamations/{code}/commentaire", json={"contenu": "ok"})
    assert r.status_code == 200
