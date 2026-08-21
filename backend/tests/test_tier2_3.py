"""Tests Tier 2 & 3 : pagination, templates, doublons, validation hiérarchique,
exports formatés, rétention RGPD, multi-entité."""
from datetime import datetime, timedelta
import pyotp


# ===== Pagination =====

def test_pagination_total_dans_header(client, payload_minimal):
    for i in range(7):
        payload_minimal["client"]["email"] = f"u{i}@x.ci"
        client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/reclamations?limit=3")
    assert r.status_code == 200
    assert r.headers.get("X-Total-Count") == "7"
    assert r.headers.get("X-Page-Limit") == "3"
    assert len(r.json()) == 3


def test_pagination_skip(client, payload_minimal):
    for i in range(5):
        payload_minimal["client"]["email"] = f"u{i}@x.ci"
        client.post("/api/reclamations", json=payload_minimal)
    page1 = client.get("/api/reclamations?limit=2&skip=0").json()
    page2 = client.get("/api/reclamations?limit=2&skip=2").json()
    page3 = client.get("/api/reclamations?limit=2&skip=4").json()
    assert len(page1) == 2 and len(page2) == 2 and len(page3) == 1
    codes = {r["code"] for r in page1 + page2 + page3}
    assert len(codes) == 5


# ===== Templates =====

def test_creer_template(client):
    r = client.post("/api/templates", json={
        "code": "TEST_TPL", "libelle": "Test", "sujet": "Sujet test",
        "corps": "Bonjour {client.prenom}, votre dossier {reclamation.code}.",
    })
    assert r.status_code == 201
    assert r.json()["code"] == "TEST_TPL"


def test_lister_templates(client):
    r_post = client.post("/api/templates", json={
        "code": "TPL1", "libelle": "TPL1 libelle",
        "sujet": "Sujet test", "corps": "Bonjour test corps long",
    })
    assert r_post.status_code == 201, r_post.text
    r = client.get("/api/templates")
    assert r.status_code == 200
    codes = {t["code"] for t in r.json()}
    assert "TPL1" in codes


def test_agent_ne_peut_pas_creer_template(agent_client):
    r = agent_client.post("/api/templates", json={
        "code": "X", "libelle": "X", "sujet": "x", "corps": "longue chaine",
    })
    assert r.status_code == 403


def test_rendu_template(client, payload_minimal):
    t = client.post("/api/templates", json={
        "code": "REND", "libelle": "Rendu",
        "sujet": "Dossier {reclamation.code} de {client.prenom}",
        "corps": "Bonjour {client.prenom} {client.nom}, votre dossier {reclamation.code} "
                 "({reclamation.categorie}) reçu le {reclamation.date_reception}.",
    }).json()
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(f"/api/templates/{t['id']}/rendre",
                    json={"code_reclamation": code})
    assert r.status_code == 200
    d = r.json()
    assert code in d["sujet"]
    assert payload_minimal["client"]["prenom"] in d["sujet"]
    assert payload_minimal["client"]["nom"] in d["corps"]
    assert "FINANCIERE" in d["corps"]


# ===== Doublons =====

def test_detection_doublons_meme_email(client, payload_minimal):
    """Même client + même catégorie sous 7 j → signalé."""
    code1 = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post("/api/reclamations/detecter-doublons", json={
        "email": payload_minimal["client"]["email"],
        "categorie": payload_minimal["categorie"],
        "sous_categorie": payload_minimal["sous_categorie"],
        "description": payload_minimal["description"],
    })
    assert r.status_code == 200
    d = r.json()
    assert d["nb_potentiels"] >= 1
    assert any(it["code"] == code1 for it in d["doublons"])


def test_detection_doublons_aucun_match(client):
    r = client.post("/api/reclamations/detecter-doublons", json={
        "email": "ghost@nulle-part.ci",
        "categorie": "FRAUDE",
        "description": "Texte unique sans correspondance ailleurs.",
    })
    assert r.status_code == 200
    assert r.json()["nb_potentiels"] == 0


# ===== Validation hiérarchique =====

def test_chaine_approbation_complete(client, payload_minimal):
    """Initier → approuver niveaux 1 et 2 → passage en DECISION."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    # Aller en EN_COURS pour avoir le droit de passer en VALIDATION
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})

    r = client.post(f"/api/reclamations/{code}/approbations/initier",
                    json={"roles_chaine": ["GESTIONNAIRE", "SUPERVISEUR"]})
    assert r.status_code == 201
    niveaux = r.json()
    assert len(niveaux) == 2

    # L'admin peut approuver tous les niveaux
    r1 = client.post(f"/api/reclamations/{code}/approbations/{niveaux[0]['id']}/approuver",
                     json={"commentaire": "OK gestionnaire"})
    assert r1.status_code == 200

    d = client.get(f"/api/reclamations/{code}").json()
    assert d["statut"] == "VALIDATION"  # pas encore tous approuvés

    r2 = client.post(f"/api/reclamations/{code}/approbations/{niveaux[1]['id']}/approuver",
                     json={"commentaire": "OK superviseur"})
    assert r2.status_code == 200

    d = client.get(f"/api/reclamations/{code}").json()
    assert d["statut"] == "DECISION"


def test_chaine_approbation_ordre_strict(client, payload_minimal):
    """Impossible d'approuver le niveau 2 avant le niveau 1."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    niveaux = client.post(f"/api/reclamations/{code}/approbations/initier",
                          json={"roles_chaine": ["GESTIONNAIRE", "SUPERVISEUR"]}).json()
    # On tente directement le 2e
    r = client.post(f"/api/reclamations/{code}/approbations/{niveaux[1]['id']}/approuver",
                    json={})
    assert r.status_code == 409


def test_rejet_renvoie_en_cours(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    for s in ["QUALIF", "AFFECTE", "EN_COURS"]:
        client.post(f"/api/reclamations/{code}/statut", json={"nouveau_statut": s})
    niveaux = client.post(f"/api/reclamations/{code}/approbations/initier",
                          json={"roles_chaine": ["GESTIONNAIRE"]}).json()
    r = client.post(f"/api/reclamations/{code}/approbations/{niveaux[0]['id']}/rejeter",
                    json={"commentaire": "Dossier incomplet"})
    assert r.status_code == 200
    d = client.get(f"/api/reclamations/{code}").json()
    assert d["statut"] == "EN_COURS"


# ===== Exports Excel + PDF =====

def test_export_xlsx(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/exports/registre.xlsx")
    assert r.status_code == 200
    assert "spreadsheet" in r.headers["content-type"]
    # Un xlsx commence par PK (zip)
    assert r.content[:2] == b"PK"


def test_export_pdf(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/exports/registre.pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_rapport_mensuel(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    now = datetime.utcnow()
    r = client.get(f"/api/exports/rapport-mensuel.pdf?annee={now.year}&mois={now.month}")
    assert r.status_code == 200
    assert r.content[:4] == b"%PDF"


def test_rapport_mensuel_mois_invalide(client):
    r = client.get("/api/exports/rapport-mensuel.pdf?annee=2026&mois=13")
    assert r.status_code == 422


def test_exports_agent_refuse(agent_client):
    assert agent_client.get("/api/exports/registre.xlsx").status_code == 403
    assert agent_client.get("/api/exports/registre.pdf").status_code == 403


# ===== Rétention RGPD =====

def test_anonymisation_rgpd(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(f"/api/admin/retention/{code}/anonymiser-rgpd")
    assert r.status_code == 204
    d = client.get(f"/api/reclamations/{code}").json()
    assert d["client"]["nom"] == "ANONYMISÉ"
    assert d["client"]["email"] is None
    assert "anonymisée" in d["description"].lower()


def test_anonymisation_rgpd_idempotent(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(f"/api/admin/retention/{code}/anonymiser-rgpd")
    r = client.post(f"/api/admin/retention/{code}/anonymiser-rgpd")
    assert r.status_code == 409


def test_candidats_retention_vide_au_demarrage(client):
    r = client.get("/api/admin/retention/candidats").json()
    assert r["nb_archivage"] == 0
    assert r["nb_anonymisation"] == 0


def test_retention_admin_only(agent_client):
    assert agent_client.get("/api/admin/retention/candidats").status_code == 403
    assert agent_client.post("/api/admin/retention/appliquer").status_code == 403


# ===== Notifications SSE =====

def test_sse_endpoint_existe(anon_client):
    """Un appel sans token sur /stream renvoie 401, pas 404."""
    r = anon_client.get("/api/notifications/stream?token=invalide")
    assert r.status_code == 401
