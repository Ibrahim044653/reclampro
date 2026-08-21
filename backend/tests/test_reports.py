"""Endpoints /api/reports — admin only."""


def test_reports_admin_only(agent_client):
    assert agent_client.get("/api/reports/synthese").status_code == 403
    assert agent_client.get("/api/reports/par-dimension?dim=categorie").status_code == 403
    assert agent_client.get("/api/reports/serie-temporelle").status_code == 403
    assert agent_client.get("/api/reports/conformite-sla").status_code == 403


def test_synthese_periode_mois(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/reports/synthese?periode=mois").json()
    assert r["periode"] == "mois"
    assert r["total_recues"] >= 1
    assert "delai_moyen_traitement_heures" in r
    assert "taux_conformite_sla" in r


def test_synthese_toutes_periodes(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    for p in ("semaine", "mois", "trimestre", "annee"):
        r = client.get(f"/api/reports/synthese?periode={p}")
        assert r.status_code == 200, p
        assert r.json()["periode"] == p


def test_periode_invalide(client):
    r = client.get("/api/reports/synthese?periode=siecle")
    assert r.status_code == 422


def test_par_dimension_categorie(client, payload_minimal):
    payload_minimal["categorie"] = "FRAUDE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["categorie"] = "SERVICE"
    payload_minimal["client"]["email"] = "z@z.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reports/par-dimension?dim=categorie&periode=annee").json()
    assert r["dimension"] == "categorie"
    modalites = {it["modalite"] for it in r["items"]}
    assert "FRAUDE" in modalites
    assert "SERVICE" in modalites


def test_par_dimension_invalide(client):
    r = client.get("/api/reports/par-dimension?dim=meteo")
    assert r.status_code == 422


def test_serie_temporelle(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    r = client.get("/api/reports/serie-temporelle?granularite=mois&points=6").json()
    assert len(r["points"]) == 6
    assert sum(p["recues"] for p in r["points"]) >= 1


def test_serie_temporelle_granularites(client, payload_minimal):
    client.post("/api/reclamations", json=payload_minimal)
    for g in ("jour", "semaine", "mois", "annee"):
        r = client.get(f"/api/reports/serie-temporelle?granularite={g}&points=3").json()
        assert len(r["points"]) == 3, g


def test_conformite_sla(client, payload_minimal):
    payload_minimal["priorite"] = "CRITIQUE"
    client.post("/api/reclamations", json=payload_minimal)
    payload_minimal["priorite"] = "STANDARD"
    payload_minimal["client"]["email"] = "x@x.ci"
    client.post("/api/reclamations", json=payload_minimal)

    r = client.get("/api/reports/conformite-sla?dim=priorite&periode=annee").json()
    assert r["dimension"] == "priorite"
    assert all("conformite_pct" in it for it in r["items"])
