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


def rappeler_agents_echeance(db: Session) -> dict:
    """Envoie un email à l'agent assigné pour chaque dossier à moins de 24h de l'échéance.

    Idempotent sur la même journée : si plusieurs crons tournent dans la journée,
    le rappel peut être envoyé plusieurs fois (acceptable — pas de flag d'envoi).
    """
    from datetime import timedelta
    from . import communication
    now = datetime.utcnow()
    fenetre_fin = now + timedelta(hours=24)

    recs = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.statut.in_(STATUTS_ESCALADABLES),
            models.Reclamation.date_echeance_sla > now,
            models.Reclamation.date_echeance_sla <= fenetre_fin,
            models.Reclamation.archivee == False,
        )
    ))

    rappels = 0
    for r in recs:
        agent = r.agent_affecte
        if not agent or not agent.email_pro:
            continue
        heures = (r.date_echeance_sla - now).total_seconds() / 3600
        sujet = f"[RéclamPro] Rappel SLA : dossier {r.code} expire dans {heures:.0f}h"
        corps = (
            f"Bonjour {agent.prenom} {agent.nom},\n\n"
            f"Le dossier {r.code} ({r.categorie} · {r.priorite}) expire dans "
            f"environ {heures:.0f} heures.\n"
            f"Échéance : {r.date_echeance_sla.strftime('%d/%m/%Y %H:%M')} UTC\n\n"
            f"Merci d'agir rapidement pour respecter le délai réglementaire.\n\n"
            f"RéclamPro — Gestion des réclamations BCEAO/CIMA\n"
        )
        communication.envoyer_email(agent.email_pro, sujet, corps)
        rappels += 1

    return {"verifies": len(recs), "rappels": rappels, "ts": now.isoformat()}
