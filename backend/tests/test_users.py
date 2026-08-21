"""Gestion utilisateurs — admin only."""


def test_agent_ne_peut_pas_lister_users(agent_client):
    assert agent_client.get("/api/users").status_code == 403


def test_admin_liste_users(client):
    r = client.get("/api/users")
    assert r.status_code == 200
    items = r.json()
    assert any(u["username"] == "admin" for u in items)
    assert any(u["username"] == "agent" for u in items)


def test_admin_cree_user(client):
    payload = {
        "nom": "Yao", "prenom": "Akissi", "email_pro": "ayao@sib.ci",
        "role": "GESTIONNAIRE", "service": "Back-office",
        "username": "ayao", "password": "azerty123",
    }
    r = client.post("/api/users", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["username"] == "ayao"
    assert data["role"] == "GESTIONNAIRE"


def test_username_unique(client):
    payload = {
        "nom": "X", "prenom": "Y", "email_pro": "x@y.ci",
        "role": "AGENT", "username": "admin", "password": "azerty123",
    }
    r = client.post("/api/users", json=payload)
    assert r.status_code == 409


def test_role_invalide_refuse(client):
    payload = {
        "nom": "Test", "prenom": "Role", "email_pro": "tr@sib.ci",
        "role": "DIEU", "username": "trole", "password": "azerty123",
    }
    r = client.post("/api/users", json=payload)
    assert r.status_code == 422


def test_password_trop_court(client):
    payload = {
        "nom": "Test", "prenom": "PWD", "email_pro": "pwd@sib.ci",
        "role": "AGENT", "username": "pwd", "password": "1234",
    }
    r = client.post("/api/users", json=payload)
    assert r.status_code == 422


def test_modifier_user(client):
    user_id = client.post("/api/users", json={
        "nom": "A", "prenom": "B", "email_pro": "ab@sib.ci",
        "role": "AGENT", "username": "ab1", "password": "azerty123",
    }).json()["id"]
    r = client.patch(f"/api/users/{user_id}", json={"role": "SUPERVISEUR", "actif": False})
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "SUPERVISEUR"
    assert data["actif"] is False


def test_admin_ne_peut_pas_se_desactiver(client):
    me = next(u for u in client.get("/api/users").json() if u["username"] == "admin")
    r = client.patch(f"/api/users/{me['id']}", json={"actif": False})
    assert r.status_code == 409


def test_reset_password(client, anon_client):
    user_id = client.post("/api/users", json={
        "nom": "Pwd", "prenom": "Reset", "email_pro": "pr@sib.ci",
        "role": "AGENT", "username": "preset", "password": "azerty123",
    }).json()["id"]

    r = client.post(f"/api/users/{user_id}/password", json={"new_password": "nouveau999"})
    assert r.status_code == 204

    # On vérifie qu'on se connecte avec le nouveau mdp et plus avec l'ancien.
    ko = anon_client.post("/api/auth/login", json={"username": "preset", "password": "azerty123"})
    assert ko.status_code == 401
    ok = anon_client.post("/api/auth/login", json={"username": "preset", "password": "nouveau999"})
    assert ok.status_code == 200


def test_desactivation_empeche_login(client, anon_client):
    user_id = client.post("/api/users", json={
        "nom": "Tmp", "prenom": "User", "email_pro": "tmp@sib.ci",
        "role": "AGENT", "username": "tmpuser", "password": "azerty123",
    }).json()["id"]

    client.delete(f"/api/users/{user_id}")

    ko = anon_client.post("/api/auth/login", json={"username": "tmpuser", "password": "azerty123"})
    assert ko.status_code == 401


def test_dashboard_etendu_contient_nouveaux_champs(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    d = client.get("/api/dashboard").json()
    assert "repartition_priorite" in d
    assert "repartition_sla" in d
    assert "volume_mensuel" in d
    assert "echeances_jour" in d
    assert "aujourd_hui" in d
