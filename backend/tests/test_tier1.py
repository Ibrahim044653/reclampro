"""Tests Tier 1 : chiffrement, pièces jointes, MFA, portail public, email driver."""
import io
import pyotp


# ===== Chiffrement =====

def test_chiffrement_email_en_base(client, payload_minimal, db_engine):
    """L'email du client n'est PAS stocké en clair en base."""
    from sqlalchemy import text
    client.post("/api/reclamations", json=payload_minimal)

    with db_engine.connect() as conn:
        rows = conn.execute(text("SELECT email FROM clients")).fetchall()
    emails_db = [r[0] for r in rows]
    assert any(emails_db), "Aucun client trouvé"
    # Le token Fernet commence par "gAAAAA" en base64 URL-safe
    assert all(e is None or e.startswith("gAAAA") for e in emails_db), \
        f"Email stocké en clair : {emails_db}"


def test_chiffrement_lecture_transparente(client, payload_minimal):
    """L'API rend l'email en clair (déchiffrement transparent)."""
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    d = client.get(f"/api/reclamations/{code}").json()
    assert d["client"]["email"] == payload_minimal["client"]["email"]


def test_deduplication_par_email_hash(client, payload_minimal):
    """Deux réclamations avec le même email réutilisent le même client (via email_hash)."""
    r1 = client.post("/api/reclamations", json=payload_minimal).json()
    r2 = client.post("/api/reclamations", json=payload_minimal).json()
    assert r1["client"]["id"] == r2["client"]["id"]


# ===== Pièces jointes =====

def test_upload_pj_succes(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("test.txt", b"contenu test", "text/plain")},
    )
    assert r.status_code == 201, r.text
    pj = r.json()
    assert pj["nom_fichier"] == "test.txt"
    assert pj["taille_octets"] == 12
    assert len(pj["checksum_sha256"]) == 64


def test_upload_pj_mime_refuse(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("malware.exe", b"MZ\x00\x00", "application/x-msdownload")},
    )
    assert r.status_code == 422


def test_upload_pj_vide_refuse(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("vide.txt", b"", "text/plain")},
    )
    assert r.status_code == 422


def test_telechargement_pj(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    pj_id = client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("doc.txt", b"contenu specifique", "text/plain")},
    ).json()["id"]
    r = client.get(f"/api/pieces-jointes/{pj_id}/telecharger")
    assert r.status_code == 200
    assert r.content == b"contenu specifique"


def test_lister_pj(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("a.txt", b"AAA", "text/plain")},
    )
    client.post(
        f"/api/reclamations/{code}/pieces-jointes",
        files={"fichier": ("b.txt", b"BBB", "text/plain")},
    )
    r = client.get(f"/api/reclamations/{code}/pieces-jointes")
    assert r.status_code == 200
    assert len(r.json()) == 2


# ===== MFA =====

def test_mfa_setup_genere_secret_et_qr(client):
    r = client.post("/api/auth/mfa/setup")
    assert r.status_code == 200
    d = r.json()
    assert "secret" in d and len(d["secret"]) >= 16
    assert d["uri"].startswith("otpauth://totp/")
    assert len(d["qr_code_png_base64"]) > 500


def test_mfa_activation_avec_code_valide(client):
    secret = client.post("/api/auth/mfa/setup").json()["secret"]
    code = pyotp.TOTP(secret).now()
    r = client.post("/api/auth/mfa/activate", json={"code": code})
    assert r.status_code == 204
    me = client.get("/api/auth/me").json()
    assert me["mfa_active"] is True


def test_mfa_activation_code_invalide(client):
    client.post("/api/auth/mfa/setup")
    r = client.post("/api/auth/mfa/activate", json={"code": "000000"})
    assert r.status_code == 401


def test_login_demande_mfa_apres_activation(client, anon_client):
    secret = client.post("/api/auth/mfa/setup").json()["secret"]
    code = pyotp.TOTP(secret).now()
    client.post("/api/auth/mfa/activate", json={"code": code})

    # Tentative login sans code → MFA_REQUIRED
    r = anon_client.post("/api/auth/login",
                         json={"username": "admin", "password": "admin123"})
    assert r.status_code == 401
    assert r.json()["detail"] == "MFA_REQUIRED"

    # Avec code valide → OK
    code = pyotp.TOTP(secret).now()
    r = anon_client.post("/api/auth/login",
                         json={"username": "admin", "password": "admin123", "code_mfa": code})
    assert r.status_code == 200
    assert r.json()["utilisateur"]["mfa_active"] is True


def test_mfa_desactivation_protege_par_mot_de_passe(client):
    secret = client.post("/api/auth/mfa/setup").json()["secret"]
    client.post("/api/auth/mfa/activate", json={"code": pyotp.TOTP(secret).now()})

    ko = client.post("/api/auth/mfa/desactiver", json={"password": "wrong"})
    assert ko.status_code == 401

    ok = client.post("/api/auth/mfa/desactiver", json={"password": "admin123"})
    assert ok.status_code == 204
    me = client.get("/api/auth/me").json()
    assert me["mfa_active"] is False


# ===== Portail public =====

def test_portail_soumission_sans_auth(anon_client):
    payload = {
        "canal": "WEB",
        "categorie": "SERVICE", "sous_categorie": "Test",
        "priorite": "STANDARD",
        "description": "Test de soumission publique depuis le portail.",
        "montant_enjeu": 0,
        "client": {"nom": "Public", "prenom": "Anon",
                   "email": "anon@test.ci", "telephone": "+225 00"},
    }
    r = anon_client.post("/api/public/reclamations", json=payload)
    assert r.status_code == 201
    d = r.json()
    assert d["code"].startswith("RECB-")
    assert len(d["token_suivi"]) > 20
    assert "/portail-suivi.html?token=" in d["url_suivi"]


def test_portail_suivi_via_token(anon_client):
    token = anon_client.post("/api/public/reclamations", json={
        "canal": "WEB", "categorie": "SERVICE", "priorite": "STANDARD",
        "description": "Description pour test suivi public.",
        "client": {"nom": "X", "prenom": "Y", "email": "xy@test.ci"},
    }).json()["token_suivi"]

    r = anon_client.get(f"/api/public/reclamations/{token}")
    assert r.status_code == 200
    d = r.json()
    assert d["statut"] == "NOUVEAU"
    assert d["statut_libelle"] == "Reçu"
    types = {i["type"] for i in d["interactions_publiques"]}
    assert "CREATION" in types and "ACR" in types


def test_portail_suivi_token_invalide(anon_client):
    r = anon_client.get("/api/public/reclamations/" + "X" * 30)
    assert r.status_code == 404


def test_portail_suivi_ne_revele_pas_audit_interne(anon_client, client):
    """Le journal d'audit interne (AFFECTATION etc.) n'est pas visible côté public."""
    submission = anon_client.post("/api/public/reclamations", json={
        "canal": "WEB", "categorie": "SERVICE", "priorite": "STANDARD",
        "description": "Description pour test audit caché.",
        "client": {"nom": "X", "prenom": "Y", "email": "audittest@x.ci"},
    }).json()
    token = submission["token_suivi"]
    code = submission["code"]
    client.post(f"/api/reclamations/{code}/commentaire", json={"contenu": "note interne"})

    pub = anon_client.get(f"/api/public/reclamations/{token}").json()
    types = {i["type"] for i in pub["interactions_publiques"]}
    assert "COMMENTAIRE" not in types


# ===== Service communication (driver console par défaut) =====

def test_template_acr_contient_code_dossier(client, payload_minimal):
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    d = client.get(f"/api/reclamations/{code}").json()
    types_journal = [i["type"] for i in d["interactions"]]
    contenus_acr = [i["contenu"] for i in d["interactions"] if i["type"] == "ACR"]
    assert "ACR" in types_journal
    assert any("SIMULE" in c or "ENVOYE" in c for c in contenus_acr)
    assert any(payload_minimal["client"]["email"] in c for c in contenus_acr)
