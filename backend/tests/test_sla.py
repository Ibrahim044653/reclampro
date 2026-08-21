"""RG001-RG004 — calcul d'échéance et seuils d'alerte SLA."""
from datetime import datetime, timedelta

from app.services.sla import calculer_echeance, pourcentage_consomme, statut_sla


def test_echeance_standard_5j():
    reception = datetime(2025, 5, 1, 9, 0)
    e = calculer_echeance(reception, "STANDARD")
    assert e == reception + timedelta(hours=120)


def test_echeance_urgent_72h():
    reception = datetime(2025, 5, 1, 9, 0)
    assert calculer_echeance(reception, "URGENT") == reception + timedelta(hours=72)


def test_echeance_critique_24h():
    reception = datetime(2025, 5, 1, 9, 0)
    assert calculer_echeance(reception, "CRITIQUE") == reception + timedelta(hours=24)


def test_alerte_a_80pct(db_session):
    reception = datetime(2025, 5, 1)
    echeance = calculer_echeance(reception, "STANDARD")
    a_70 = reception + timedelta(hours=int(120 * 0.7))
    a_85 = reception + timedelta(hours=int(120 * 0.85))
    assert statut_sla(reception, echeance, "EN_COURS", now=a_70) == "OK"
    assert statut_sla(reception, echeance, "EN_COURS", now=a_85) == "ALERTE"


def test_echu_au_dela_de_100pct():
    reception = datetime(2025, 5, 1)
    echeance = calculer_echeance(reception, "STANDARD")
    apres = echeance + timedelta(hours=1)
    assert statut_sla(reception, echeance, "EN_COURS", now=apres) == "ECHU"


def test_cloture_neutralise_sla():
    reception = datetime(2025, 5, 1)
    echeance = calculer_echeance(reception, "STANDARD")
    apres = echeance + timedelta(days=10)
    assert statut_sla(reception, echeance, "CLOTURE", now=apres) == "TERMINE"


def test_pourcentage_clamped():
    r = datetime(2025, 5, 1)
    e = r + timedelta(hours=24)
    assert 0 <= pourcentage_consomme(r, e, now=r) <= 1
    assert pourcentage_consomme(r, e, now=r + timedelta(hours=12)) == 0.5
