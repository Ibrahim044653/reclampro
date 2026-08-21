"""Transfert d'équipe + notification du destinataire."""


def _equipe_id(client, code):
    eqs = client.get("/api/equipes").json()
    for e in eqs:
        if e["code"] == code:
            return e["id"]
    raise AssertionError(f"Équipe {code} introuvable")


def test_transfert_simple(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_back = _equipe_id(client, "BACK")

    r = client.post(f"/api/reclamations/{code}/transfert", json={
        "id_equipe_cible": eq_back, "motif": "Investigation back-office requise",
    })
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["equipe_affectee"]["code"] == "BACK"


def test_transfert_motif_obligatoire(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_back = _equipe_id(client, "BACK")
    r = client.post(f"/api/reclamations/{code}/transfert",
                    json={"id_equipe_cible": eq_back, "motif": "x"})
    assert r.status_code == 422


def test_transfert_meme_equipe_refuse(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_back = _equipe_id(client, "BACK")
    client.post(f"/api/reclamations/{code}/transfert",
                json={"id_equipe_cible": eq_back, "motif": "premier transfert"})
    r = client.post(f"/api/reclamations/{code}/transfert",
                    json={"id_equipe_cible": eq_back, "motif": "doublon"})
    assert r.status_code == 409


def test_transfert_cree_notification_pour_membres_equipe(client, agent_client, payload_minimal):
    """Quand l'admin (équipe BACK) transfère vers FRONT, le user 'agent' (équipe FRONT)
    doit recevoir une notification."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_front = _equipe_id(client, "FRONT")

    before = agent_client.get("/api/notifications/count").json()["non_lues"]
    client.post(f"/api/reclamations/{code}/transfert",
                json={"id_equipe_cible": eq_front, "motif": "investigation front-office"})
    after = agent_client.get("/api/notifications/count").json()["non_lues"]
    assert after == before + 1

    notifs = agent_client.get("/api/notifications").json()
    assert notifs[0]["type"] == "TRANSFERT"
    assert code in notifs[0]["contenu"]
    assert notifs[0]["code_reclamation"] == code
    assert notifs[0]["lue"] is False


def test_affectation_notifie_l_agent_cible(client, agent_client, payload_minimal):
    """Affecter à un agent autre que soi crée une notification pour lui."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    # Liste des agents pour récupérer l'id du compte 'agent'
    users = client.get("/api/users").json()
    agent = next(u for u in users if u["username"] == "agent")

    client.post(f"/api/reclamations/{code}/affectation",
                json={"id_agent_affecte": agent["id"]})

    notifs = agent_client.get("/api/notifications").json()
    assert any(n["type"] == "AFFECTATION" and n["code_reclamation"] == code for n in notifs)


def test_marquer_notification_lue(client, agent_client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_front = _equipe_id(client, "FRONT")
    client.post(f"/api/reclamations/{code}/transfert",
                json={"id_equipe_cible": eq_front, "motif": "test marquage"})

    notif_id = agent_client.get("/api/notifications").json()[0]["id"]
    assert agent_client.post(f"/api/notifications/{notif_id}/lue").status_code == 204
    refreshed = agent_client.get("/api/notifications").json()[0]
    assert refreshed["lue"] is True


def test_tout_marquer_lu(client, agent_client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    eq_front = _equipe_id(client, "FRONT")
    client.post(f"/api/reclamations/{code}/transfert",
                json={"id_equipe_cible": eq_front, "motif": "test marquage bulk"})

    assert agent_client.get("/api/notifications/count").json()["non_lues"] >= 1
    agent_client.post("/api/notifications/toutes-lues")
    assert agent_client.get("/api/notifications/count").json()["non_lues"] == 0
