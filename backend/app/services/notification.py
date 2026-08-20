"""Création de notifications ciblées.

Utilisé lors d'un transfert d'équipe pour prévenir les membres du destinataire,
et lors d'une affectation pour prévenir l'agent ciblé.
"""
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models


def notifier_agent(
    db: Session,
    agent_id: int,
    type_notif: str,
    contenu: str,
    reclamation: models.Reclamation | None = None,
) -> models.Notification:
    n = models.Notification(
        id_destinataire=agent_id,
        type=type_notif,
        contenu=contenu,
        id_reclamation=reclamation.id if reclamation else None,
        code_reclamation=reclamation.code if reclamation else None,
    )
    db.add(n)
    db.flush()
    return n


def notifier_equipe(
    db: Session,
    equipe_id: int,
    type_notif: str,
    contenu: str,
    reclamation: models.Reclamation | None = None,
    exclus: set[int] | None = None,
) -> int:
    """Crée une notification par membre actif de l'équipe. Retourne le nombre créé."""
    exclus = exclus or set()
    membres = list(db.scalars(
        select(models.Agent).where(
            models.Agent.id_equipe == equipe_id,
            models.Agent.actif == True,
        )
    ))
    count = 0
    for m in membres:
        if m.id in exclus:
            continue
        notifier_agent(db, m.id, type_notif, contenu, reclamation)
        count += 1
    return count
