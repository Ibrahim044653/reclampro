"""Annexe A — transitions de statut autorisées uniquement."""
from app.services.workflow import transition_autorisee, statuts_suivants_possibles


def test_transition_classique_autorisee():
    assert transition_autorisee("NOUVEAU", "QUALIF")
    assert transition_autorisee("EN_COURS", "VALIDATION")
    assert transition_autorisee("DECISION", "CLOTURE")


def test_transition_inverse_refusee():
    assert not transition_autorisee("CLOTURE", "EN_COURS")
    assert not transition_autorisee("QUALIF", "NOUVEAU")


def test_rejete_est_final():
    assert statuts_suivants_possibles("REJETE") == []


def test_seul_superviseur_reouvre():
    assert "REOUVRE" in statuts_suivants_possibles("CLOTURE")
