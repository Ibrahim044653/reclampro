"""Escalade automatique des dossiers proches de l'échéance SLA (BR007).

Logique :
- Vérifie tous les dossiers ouverts (non clôturés, non archivés).
- Si le délai consommé dépasse SEUIL_ALERTE_SLA (80%), passe le statut à ALERTE.
- Idempotent : un dossier déjà en ALERTE ou ESCALADE n'est pas re-traité.
- Enregistre une interaction immuable pour chaque escalade.
"""
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import SEUIL_ALERTE_SLA
from .sla import pourcentage_consomme
from . import audit

STATUTS_ESCALADABLES = {"NOUVEAU", "QUALIF", "AFFECTE", "EN_COURS", "ATT_CLIENT"}


def escalader_dossiers_en_retard(db: Session) -> dict:
    """Passe à ALERTE tous les dossiers dont le SLA est consommé à plus de SEUIL_ALERTE_SLA.

    Retourne un dict : {"verifies": N, "escalades": M, "ts": ISO}.
    """
    now = datetime.utcnow()
    recs = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.statut.in_(STATUTS_ESCALADABLES),
            models.Reclamation.archivee == False,
        )
    ))

    escalades = 0
    for r in recs:
        pct = pourcentage_consomme(r.date_reception, r.date_echeance_sla, now)
        if pct < SEUIL_ALERTE_SLA:
            continue
        ancien = r.statut
        r.statut = "ALERTE"
        audit.enregistrer(
            db, r.id, "CHANGEMENT_STATUT",
            f"Alerte SLA automatique : {pct * 100:.0f}% du délai consommé. "
            f"Statut précédent : {ancien}.",
            auteur="système/cron",
            valeur_avant=ancien,
            valeur_apres="ALERTE",
        )
        escalades += 1

    if escalades:
        db.commit()

    return {"verifies": len(recs), "escalades": escalades, "ts": now.isoformat()}
