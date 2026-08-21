"""Filtres avancés sur la liste des réclamations."""
from datetime import datetime, timedelta


def _creer(client, payload_minimal, **overrides):
    p = {**payload_minimal, **overrides}
    if "email" in overrides:
        p["client"] = {**p["client"], "email": overrides.pop("email")}
    return client.post("/api/reclamations", json=p).json()["code"]


def test_filtre_priorite(client, payload_minimal):
    payload_minimal["priorite"] = "CRITIQUE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["priorite"] = "STANDARD"
    payload_minimal["client"]["email"] = "a@b.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reclamations?priorite=CRITIQUE").json()
    assert len(r) == 1 and r[0]["priorite"] == "CRITIQUE"


def test_filtre_categorie(client, payload_minimal):
    payload_minimal["categorie"] = "FRAUDE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["categorie"] = "SERVICE"
    payload_minimal["client"]["email"] = "b@b.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reclamations?categorie=FRAUDE").json()
    assert len(r) == 1 and r[0]["categorie"] == "FRAUDE"


def test_filtre_canal(client, payload_minimal):
    payload_minimal["canal"] = "WHATSAPP"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["canal"] = "EMAIL"
    payload_minimal["client"]["email"] = "c@c.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reclamations?canal=WHATSAPP").json()
    assert len(r) == 1 and r[0]["canal"] == "WHATSAPP"


def test_filtre_recherche_texte(client, payload_minimal):
    payload_minimal["description"] = "Description avec le mot magique inrouvable ailleurs."
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["description"] = "Une description toute simple sans mot particulier."
    payload_minimal["client"]["email"] = "d@d.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reclamations?q=magique").json()
    assert len(r) == 1
    assert "magique" in r[0]["description"]


def test_filtre_dates(client, payload_minimal):
    """Test que les bornes de date sont respectées."""
    client.post("/api/reclamations", json=payload_minimal)

    futur = (datetime.utcnow() + timedelta(days=1)).isoformat()
    r = client.get(f"/api/reclamations?date_debut={futur}").json()
    assert len(r) == 0

    passe = (datetime.utcnow() - timedelta(days=1)).isoformat()
    r = client.get(f"/api/reclamations?date_debut={passe}").json()
    assert len(r) == 1


def test_filtres_combinees(client, payload_minimal):
    payload_minimal["priorite"] = "CRITIQUE"
    payload_minimal["categorie"] = "FRAUDE"
    payload_minimal["canal"] = "AGENCE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["priorite"] = "CRITIQUE"
    payload_minimal["categorie"] = "SERVICE"
    payload_minimal["client"]["email"] = "e@e.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reclamations?priorite=CRITIQUE&categorie=FRAUDE").json()
    assert len(r) == 1 and r[0]["categorie"] == "FRAUDE"
