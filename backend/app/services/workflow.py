"""Règles de transition de statut (Annexe A du CDC).

On refuse toute transition non listée — c'est la garantie que le workflow
reste piloté par le système et non par les agents (BR001 + RG005).
"""

TRANSITIONS = {
    "NOUVEAU": {"QUALIF", "REJETE"},
    "QUALIF": {"AFFECTE", "REJETE"},
    "AFFECTE": {"EN_COURS"},
    "EN_COURS": {"ATT_CLIENT", "VALIDATION", "ALERTE", "ESCALADE"},
    "ATT_CLIENT": {"EN_COURS"},
    "ALERTE": {"EN_COURS", "ESCALADE"},
    "ESCALADE": {"EN_COURS", "VALIDATION"},
    "VALIDATION": {"DECISION", "EN_COURS"},
    "DECISION": {"CLOTURE", "REOUVRE"},
    "CLOTURE": {"REOUVRE"},
    "REOUVRE": {"EN_COURS"},
    "REJETE": set(),
}

STATUTS_FINAUX = {"CLOTURE", "REJETE"}

# Catégories de pilotage opérationnel.
STATUTS_A_TRAITER = {"NOUVEAU", "QUALIF", "AFFECTE", "ATT_CLIENT"}
STATUTS_EN_COURS = {"EN_COURS", "ALERTE", "ESCALADE", "VALIDATION", "DECISION", "REOUVRE"}
STATUTS_TRAITES = {"CLOTURE", "REJETE"}


def categorie_pilotage(statut: str) -> str:
    """Regroupe les statuts en 3 catégories pour le pilotage agent/équipe."""
    if statut in STATUTS_A_TRAITER:
        return "a_traiter"
    if statut in STATUTS_TRAITES:
        return "traites"
    return "en_cours"


def transition_autorisee(courant: str, cible: str) -> bool:
    return cible in TRANSITIONS.get(courant, set())


def statuts_suivants_possibles(courant: str) -> list[str]:
    return sorted(TRANSITIONS.get(courant, set()))
