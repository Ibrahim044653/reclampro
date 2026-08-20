"""Gestion de la rétention BCEAO/CIMA (RG011) et RGPD.

- **Archivage** : dossiers clôturés depuis plus de 5 ans → marqués archivés
  (ils restent en base et exportables, mais sont sortis des vues actives).
- **Anonymisation** : dossiers clôturés depuis plus de 10 ans → données
  personnelles client effacées (nom, prénom, email, téléphone), description
  remplacée par un placeholder. Le code dossier et les méta réglementaires
  sont conservés à vie.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, config


def candidats_archivage(db: Session, now: datetime | None = None) -> list[models.Reclamation]:
    now = now or datetime.utcnow()
    seuil = now - timedelta(days=config.ARCHIVAGE_APRES_JOURS)
    stmt = (
        select(models.Reclamation)
        .where(
            models.Reclamation.statut.in_(["CLOTURE", "REJETE"]),
            models.Reclamation.date_cloture <= seuil,
            models.Reclamation.archivee == False,
        )
    )
    return list(db.scalars(stmt))


def candidats_anonymisation(db: Session, now: datetime | None = None) -> list[models.Reclamation]:
    now = now or datetime.utcnow()
    seuil = now - timedelta(days=config.ANONYMISATION_APRES_JOURS)
    stmt = (
        select(models.Reclamation)
        .where(
            models.Reclamation.statut.in_(["CLOTURE", "REJETE"]),
            models.Reclamation.date_cloture <= seuil,
            models.Reclamation.anonymisee == False,
        )
    )
    return list(db.scalars(stmt))


def archiver(db: Session, reclamation: models.Reclamation) -> None:
    reclamation.archivee = True
    reclamation.date_archivage = datetime.utcnow()


def anonymiser(db: Session, reclamation: models.Reclamation) -> None:
    """Efface les données personnelles tout en conservant la trace réglementaire."""
    client = reclamation.client
    if client:
        client.nom = "ANONYMISÉ"
        client.prenom = "—"
        client.email = None
        client.telephone = None
        client.numero_compte = None
        client.email_hash = None
    reclamation.description = "[Description anonymisée — conservation > 10 ans (RG011)]"
    reclamation.anonymisee = True
    reclamation.date_anonymisation = datetime.utcnow()
    # On garde le code, les dates, le statut, le motif de clôture.


def appliquer_retention(db: Session) -> dict:
    """Lance la politique de rétention. Retourne un résumé."""
    archives = candidats_archivage(db)
    for r in archives:
        archiver(db, r)
    anonymises = candidats_anonymisation(db)
    for r in anonymises:
        anonymiser(db, r)
    db.commit()
    return {
        "archives": [r.code for r in archives],
        "anonymises": [r.code for r in anonymises],
        "nb_archives": len(archives),
        "nb_anonymises": len(anonymises),
    }


def anonymiser_a_la_demande(db: Session, reclamation: models.Reclamation) -> None:
    """RGPD — droit à l'effacement à la demande du client.

    On ne supprime pas (contrainte réglementaire 10 ans), mais on anonymise.
    """
    anonymiser(db, reclamation)
    db.commit()
