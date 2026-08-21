"""Tests Tier 4 : Classification IA, cause racine, WhatsApp, Power BI."""


# ===== Classification IA =====

def test_ia_classifie_fraude(client):
    r = client.post("/api/reclamations/suggerer-ia", json={
        "description": "Quelqu'un a usurpé mon identité et a ouvert un compte en mon nom. C'est une fraude.",
    })
    assert r.status_code == 200
    d = r.json()
    assert d["categorie_suggeree"] == "FRAUDE"
    assert d["priorite_suggeree"] in {"CRITIQUE", "URGENT"}
    assert d["score_categorie"] > 0


def test_ia_classifie_financier(client):
    r = client.post("/api/reclamations/suggerer-ia", json={
        "description": "Un débit non autorisé de 50000 FCFA a été constaté sur mon compte.",
    }).json()
    assert r["categorie_suggeree"] == "FINANCIERE"
    assert "débit" in r["explication"] or "non autorisé" in r["explication"]


def test_ia_classifie_service(client):
    r = client.post("/api/reclamations/suggerer-ia", json={
        "description": "L'agent en agence a été très impoli et le délai d'attente était très long.",
    }).json()
    assert r["categorie_suggeree"] == "SERVICE"


def test_ia_voisinage_apprentissage(client, payload_minimal):
    """Si on a déjà créé des dossiers FRAUDE, la suggestion privilégie FRAUDE pour un texte voisin."""
    payload_minimal["categorie"] = "FRAUDE"
    payload_minimal["description"] = "Tentative de hameconnage par appel inconnu, phishing avéré."
    client.post("/api/reclamations", json=payload_minimal)

    r = client.post("/api/reclamations/suggerer-ia", json={
        "description": "Hameconnage suspect par téléphone inconnu, possible phishing.",
    }).json()
    assert r["categorie_suggeree"] == "FRAUDE"
    # Voisin reconnu
    assert len(r["voisins_similaires"]) >= 1


def test_ia_description_trop_courte(client):
    r = client.post("/api/reclamations/suggerer-ia", json={"description": "xx"})
    assert r.status_code == 422


# ===== Cause racine =====

def test_cause_racine_clusters(client, payload_minimal):
    """Crée plusieurs dossiers similaires → cluster détecté."""
    descriptions = [
        "Mon application mobile bancaire affiche un solde erroné depuis plusieurs jours.",
        "L'application mobile montre un solde incorrect et n'affiche pas les dernières opérations.",
        "Application mobile bloquée — solde affiché est incorrect et erroné.",
        "Le solde dans l'application mobile est faux. L'application bloque.",
    ]
    for i, d in enumerate(descriptions):
        payload_minimal["description"] = d
        payload_minimal["client"]["email"] = f"u{i}@x.ci"
        client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reports/causes-racines?mois=6&seuil_similarite=0.25")
    assert r.status_code == 200
    d = r.json()
    assert d["total_dossiers"] >= 4
    assert d["nb_clusters_detectes"] >= 1
    top = d["clusters"][0]
    assert top["nb_dossiers"] >= 2
    assert any("application" in m or "solde" in m for m in top["mots_cles"])


def test_cause_racine_aucun_cluster_si_isole(client, payload_minimal):
    """Une seule réclamation → 0 cluster."""
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/reports/causes-racines").json()
    assert r["nb_clusters_detectes"] == 0


# ===== WhatsApp =====

def test_whatsapp_webhook_verify_ok(anon_client):
    """Handshake Meta : on doit renvoyer le challenge."""
    r = anon_client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=dev-verify-token&hub.challenge=abc123")
    assert r.status_code == 200
    assert r.text == "abc123"


def test_whatsapp_webhook_verify_ko(anon_client):
    r = anon_client.get("/api/whatsapp/webhook?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=abc")
    assert r.status_code == 403


def test_whatsapp_webhook_message_cree_dossier(anon_client):
    """Un payload Meta valide doit créer un dossier classé par IA."""
    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "type": "text",
                        "from": "+2250700000000",
                        "id": "wamid.ABC",
                        "timestamp": "1700000000",
                        "text": {"body": "J'ai été victime de fraude sur ma carte bancaire."},
                    }],
                    "contacts": [{"profile": {"name": "Awa Konaté"}}],
                },
            }],
        }],
    }
    r = anon_client.post("/api/whatsapp/webhook", json=payload)
    assert r.status_code == 200
    d = r.json()
    assert d["statut"] == "OK"
    assert d["code_reclamation"].startswith("RECB-")


def test_whatsapp_envoyer_admin(client, payload_minimal):
    payload_minimal["client"]["telephone"] = "+2250700000001"
    code = client.post("/api/reclamations", json=payload_minimal).json()["code"]
    r = client.post("/api/whatsapp/envoyer", json={
        "code_reclamation": code,
        "message": "Bonjour, votre dossier est en cours de traitement.",
    })
    assert r.status_code == 200
    assert r.json()["statut"] in {"SIMULE", "ENVOYE"}


# ===== Power BI =====

def test_bi_reclamations_admin_only(agent_client):
    assert agent_client.get("/api/bi/reclamations").status_code == 403


def test_bi_reclamations_format_flat(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/bi/reclamations").json()
    assert "items" in r and "total" in r and "generated_at" in r
    assert r["total"] >= 1
    item = r["items"][0]
    # Champs analytiques pré-calculés
    assert "annee" in item and "mois" in item and "trimestre" in item
    assert "sla_statut" in item and "sla_pourcentage_consomme" in item


def test_bi_agregats_quotidiens(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/bi/agregats-quotidiens").json()
    assert "series" in r
    assert len(r["series"]) >= 1
    s = r["series"][0]
    assert "date" in s and "recues" in s and "par_canal" in s


def test_bi_kpi_temps_reel(client):
    r = client.get("/api/bi/kpi-temps-reel").json()
    assert "timestamp" in r
    assert "total" in r and "en_cours" in r
