"""Tests E2E des endpoints API — couvrent les exigences clés TEST-001..010."""
import re


def test_creation_dossier_genere_id_et_acr(client, payload_minimal):
    """TEST-001 — création + ACR automatique + journal initialisé."""
    r = client.post("/api/reclamations", json=payload_minimal)
    assert r.status_code == 201, r.text
    data = r.json()
    assert re.match(r"^RECB-\d{6}-\d{5}$", data["code"])
    assert data["statut"] == "NOUVEAU"
    types = [i["type"] for i in data["interactions"]]
    assert "CREATION" in types
    assert "ACR" in types


def test_creation_description_trop_courte(client, payload_minimal):
    """TEST-002 — validation : description trop courte refusée."""
    payload_minimal["description"] = "trop"
    r = client.post("/api/reclamations", json=payload_minimal)
    assert r.status_code == 422


def test_canal_invalide(client, payload_minimal):
    payload_minimal["canal"] = "PIGEON_VOYAGEUR"
    r = client.post("/api/reclamations", json=payload_minimal)
    assert r.status_code == 422


def test_transition_workflow_legale(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": "QUALIF"})
    assert r.status_code == 200
    assert r.json()["statut"] == "QUALIF"


def test_transition_workflow_illegale_refusee(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": "CLOTURE"})
    assert r.status_code == 409


def test_cloture_sans_motif_refusee(client, payload_minimal):
    """TEST-003 / RG008 — motif obligatoire."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    r = client.post(f"/api/reclamations/{code}/cloture", json={"motif": "INEXISTANT"})
    assert r.status_code == 422


def test_cloture_avec_motif_ok(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    r = client.post(f"/api/reclamations/{code}/cloture", json={"motif": "FAVORABLE"})
    assert r.status_code == 200
    d = r.json()
    assert d["statut"] == "CLOTURE"
    assert d["motif_cloture"] == "FAVORABLE"
    assert d["date_cloture"] is not None


def test_validation_obligatoire_si_montant_eleve(client, payload_minimal):
    """RG009 — montant > 500 000 FCFA bloque la clôture hors validation."""
    payload_minimal["montant_enjeu"] = 800_000
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    r = client.post(f"/api/reclamations/{code}/cloture", json={"motif": "FAVORABLE"})
    assert r.status_code == 409
    assert "500" in r.json()["detail"]


def test_journal_audit_immutable_grandit(client, payload_minimal):
    """BR002 — chaque action ajoute une ligne au journal et l'API n'expose aucun DELETE."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    n0 = len(client.get(f"/api/reclamations/{code}").json()["interactions"])
    client.post(f"/api/reclamations/{code}/commentaire", json={"contenu": "test"})
    n1 = len(client.get(f"/api/reclamations/{code}").json()["interactions"])
    assert n1 == n0 + 1
    r_delete = client.delete(f"/api/reclamations/{code}")
    assert r_delete.status_code == 405


def test_listing_filtres(client, payload_minimal):
    payload_minimal["priorite"] = "CRITIQUE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["priorite"] = "STANDARD"
    payload_minimal["client"]["email"] = "autre@example.ci"
    client.post("/api/reclamations", json=payload_minimal)

    tous = client.get("/api/reclamations").json()
    critiques = client.get("/api/reclamations?priorite=CRITIQUE").json()
    assert len(tous) == 2
    assert len(critiques) == 1
    assert critiques[0]["priorite"] == "CRITIQUE"


def test_export_registre_csv(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/exports/registre.csv")
    assert r.status_code == 200
    assert "Code dossier;Canal;Statut" in r.text
    assert "RECB-" in r.text


def test_dashboard_retourne_kpis(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["kpi"]["recues_mois"] >= 1
    assert d["kpi"]["en_cours"] >= 1
    assert "repartition_canal" in d
