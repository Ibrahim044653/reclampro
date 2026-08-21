"""Stats par agent, par équipe, et bilan personnel."""


def _equipe_id(client, code):
    return next(e["id"] for e in client.get("/api/equipes").json() if e["code"] == code)


def _user_id(client, username):
    return next(u["id"] for u in client.get("/api/users").json() if u["username"] == username)


def test_par_agent_admin_only(agent_client):
    assert agent_client.get("/api/reports/par-agent").status_code == 403


def test_par_equipe_admin_only(agent_client):
    assert agent_client.get("/api/reports/par-equipe").status_code == 403


def test_par_agent_compteurs(client, payload_minimal):
    """Création + affectation → compteurs corrects à_traiter / en_cours."""
    agent_id = _user_id(client, "agent")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/affectation", json={"id_agent_affecte": agent_id})

    data = client.get("/api/reports/par-agent?periode=annee").json()
    row = next(it for it in data["items"] if it["id_agent"] == agent_id)
    # statut passe à AFFECTE via affectation → catégorie a_traiter
    assert row["a_traiter"] == 1
    assert row["en_cours"] == 0
    assert row["traites"] == 0
    assert row["total"] == 1


def test_par_agent_compteurs_cloture(client, payload_minimal):
    agent_id = _user_id(client, "agent")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/affectation", json={"id_agent_affecte": agent_id})
    for s in ["EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})

    data = client.get("/api/reports/par-agent?periode=annee").json()
    row = next(it for it in data["items"] if it["id_agent"] == agent_id)
    assert row["en_cours"] == 1
    assert row["a_traiter"] == 0

    # clôture
    client.post(f"/api/reclamations/{code}/cloture", json={"motif": "FAVORABLE"})
    data = client.get("/api/reports/par-agent?periode=annee").json()
    row = next(it for it in data["items"] if it["id_agent"] == agent_id)
    assert row["traites"] == 1
    assert row["a_traiter"] == 0
    assert row["en_cours"] == 0


def test_par_equipe_compteurs(client, payload_minimal):
    eq_front = _equipe_id(client, "FRONT")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/transfert",
                json={"id_equipe_cible": eq_front, "motif": "test compteur"})

    data = client.get("/api/reports/par-equipe?periode=annee").json()
    row = next(it for it in data["items"] if it["id_equipe"] == eq_front)
    assert row["total"] == 1
    assert row["a_traiter"] == 1
    assert row["nb_membres_actifs"] == 1  # le user 'agent'


def test_par_equipe_inclut_non_affectees(client, payload_minimal):
    """Une réclamation créée sans affectation tombe dans 'Non affectées'."""
    client.post("/api/reclamations", json=payload_minimal)
    data = client.get("/api/reports/par-equipe?periode=annee").json()
    non_aff = next((it for it in data["items"] if it["libelle"] == "Non affectées"), None)
    assert non_aff is not None
    assert non_aff["total"] >= 1


def test_mon_bilan_authentifie(agent_client):
    r = agent_client.get("/api/reclamations/mon-bilan").json()
    assert "a_traiter" in r and "en_cours" in r and "traites" in r
    assert r["agent"]["username"] == "agent"


def test_mes_dossiers_separation(agent_client, client, payload_minimal):
    """Affecté à agent → apparaît dans /mes de agent, pas dans /mes de admin."""
    agent_id = _user_id(client, "agent")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/affectation", json={"id_agent_affecte": agent_id})

    mes_agent = agent_client.get("/api/reclamations/mes").json()
    mes_admin = client.get("/api/reclamations/mes").json()

    codes_agent = {r["code"] for r in mes_agent}
    codes_admin = {r["code"] for r in mes_admin}
    assert code in codes_agent
    assert code not in codes_admin


def test_mes_dossiers_filtre_statut_groupe(agent_client, client, payload_minimal):
    agent_id = _user_id(client, "agent")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/affectation", json={"id_agent_affecte": agent_id})

    a_traiter = agent_client.get("/api/reclamations/mes?statut_groupe=a_traiter").json()
    en_cours = agent_client.get("/api/reclamations/mes?statut_groupe=en_cours").json()
    assert any(r["code"] == code for r in a_traiter)
    assert not any(r["code"] == code for r in en_cours)


def test_filtre_par_agent_affecte_dans_liste(client, payload_minimal):
    """Drill-down depuis les reportings : filtre id_agent_affecte sur GET /api/reclamations."""
    agent_id = _user_id(client, "agent")
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/reclamations/{code}/affectation", json={"id_agent_affecte": agent_id})

    list_aff = client.get(f"/api/reclamations?id_agent_affecte={agent_id}").json()
    assert len(list_aff) == 1 and list_aff[0]["code"] == code
