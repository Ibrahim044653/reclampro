"""Chaîne d'approbation multi-niveaux pour la validation hiérarchique (FR025)."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas, crud
from ..database import get_db
from ..services import audit, notification as notif_service
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api/reclamations",
    tags=["approbations"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.get("/{code}/approbations", response_model=list[schemas.ApprobationNiveauOut])
def lister(code: str, db: Session = Depends(get_db)):
    r = crud.obtenir(db, code)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")
    return list(db.scalars(
        select(models.ApprobationNiveau)
        .where(models.ApprobationNiveau.id_reclamation == r.id)
        .order_by(models.ApprobationNiveau.ordre)
    ))


@router.post("/{code}/approbations/initier",
             response_model=list[schemas.ApprobationNiveauOut], status_code=201)
def initier(code: str, payload: schemas.InitierValidationRequest,
            db: Session = Depends(get_db),
            user: models.Agent = Depends(utilisateur_courant)):
    """Démarre une chaîne d'approbation. Passe le dossier en statut VALIDATION."""
    r = crud.obtenir(db, code)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")

    existante = db.scalar(select(models.ApprobationNiveau).where(
        models.ApprobationNiveau.id_reclamation == r.id))
    if existante:
        raise HTTPException(409, "Chaîne d'approbation déjà initiée pour ce dossier.")

    for role in payload.roles_chaine:
        if role not in schemas.ROLES:
            raise HTTPException(422, f"Rôle '{role}' invalide.")

    niveaux = []
    for i, role in enumerate(payload.roles_chaine, start=1):
        n = models.ApprobationNiveau(
            id_reclamation=r.id, ordre=i, role_requis=role,
        )
        db.add(n)
        niveaux.append(n)

    ancien = r.statut
    r.statut = "VALIDATION"
    audit.enregistrer(
        db, r.id, "INITIATION_VALIDATION",
        f"Chaîne d'approbation démarrée : {' → '.join(payload.roles_chaine)}.",
        auteur=user.username or f"agent#{user.id}",
        valeur_avant=ancien, valeur_apres="VALIDATION",
    )
    db.commit()
    for n in niveaux:
        db.refresh(n)
    return niveaux


@router.post("/{code}/approbations/{niveau_id}/approuver",
             response_model=schemas.ApprobationNiveauOut)
def approuver(code: str, niveau_id: int, payload: schemas.ApprouverNiveauRequest,
              db: Session = Depends(get_db),
              user: models.Agent = Depends(utilisateur_courant)):
    """Approuve un niveau. Vérifie que c'est le niveau courant et que le rôle correspond."""
    r = crud.obtenir(db, code)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")

    n = db.get(models.ApprobationNiveau, niveau_id)
    if not n or n.id_reclamation != r.id:
        raise HTTPException(404, "Niveau d'approbation introuvable")
    if n.approuve_par is not None:
        raise HTTPException(409, "Ce niveau est déjà approuvé.")

    niveaux = list(db.scalars(
        select(models.ApprobationNiveau)
        .where(models.ApprobationNiveau.id_reclamation == r.id)
        .order_by(models.ApprobationNiveau.ordre)
    ))
    courant = next((x for x in niveaux if x.approuve_par is None), None)
    if courant is None or courant.id != n.id:
        raise HTTPException(409, "Ce n'est pas le niveau en attente — un niveau antérieur doit être traité d'abord.")

    if user.role != n.role_requis and user.role != "ADMIN":
        raise HTTPException(
            403, f"Ce niveau requiert un utilisateur de rôle {n.role_requis} (ou ADMIN).",
        )

    n.approuve_par = user.id
    n.date_approbation = datetime.utcnow()
    n.commentaire = payload.commentaire
    audit.enregistrer(
        db, r.id, "APPROBATION",
        f"Niveau {n.ordre} ({n.role_requis}) approuvé par {user.prenom} {user.nom}."
        + (f" Commentaire : {payload.commentaire}" if payload.commentaire else ""),
        auteur=user.username or f"agent#{user.id}",
    )

    # Tous les niveaux approuvés → on passe en DECISION
    tous_ok = all(x.approuve_par is not None for x in niveaux)
    if tous_ok:
        ancien = r.statut
        r.statut = "DECISION"
        audit.enregistrer(
            db, r.id, "CHANGEMENT_STATUT",
            "Chaîne d'approbation complète — passage en DECISION.",
            auteur="système",
            valeur_avant=ancien, valeur_apres="DECISION",
        )

    db.commit()
    db.refresh(n)
    return n


@router.post("/{code}/approbations/{niveau_id}/rejeter",
             response_model=schemas.ApprobationNiveauOut)
def rejeter(code: str, niveau_id: int, payload: schemas.ApprouverNiveauRequest,
            db: Session = Depends(get_db),
            user: models.Agent = Depends(utilisateur_courant)):
    """Rejet d'un niveau → renvoie le dossier en EN_COURS."""
    r = crud.obtenir(db, code)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")
    n = db.get(models.ApprobationNiveau, niveau_id)
    if not n or n.id_reclamation != r.id:
        raise HTTPException(404, "Niveau introuvable")
    if user.role != n.role_requis and user.role != "ADMIN":
        raise HTTPException(403, f"Niveau réservé au rôle {n.role_requis}.")
    if not payload.commentaire:
        raise HTTPException(422, "Le commentaire est obligatoire pour un rejet.")

    audit.enregistrer(
        db, r.id, "REJET_APPROBATION",
        f"Niveau {n.ordre} ({n.role_requis}) rejeté par {user.prenom} {user.nom}. "
        f"Motif : {payload.commentaire}",
        auteur=user.username or f"agent#{user.id}",
    )
    ancien = r.statut
    r.statut = "EN_COURS"
    audit.enregistrer(
        db, r.id, "CHANGEMENT_STATUT",
        "Validation rejetée — retour à EN_COURS.",
        auteur="système", valeur_avant=ancien, valeur_apres="EN_COURS",
    )

    # Réinitialise les approbations (on repart de zéro à la prochaine initiation)
    for niv in list(db.scalars(
        select(models.ApprobationNiveau).where(
            models.ApprobationNiveau.id_reclamation == r.id))):
        db.delete(niv)

    db.commit()
    return schemas.ApprobationNiveauOut(
        id=n.id, ordre=n.ordre, role_requis=n.role_requis,
        approuve_par=None, date_approbation=None, commentaire=payload.commentaire,
    )
