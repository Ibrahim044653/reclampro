"""Gestion des utilisateurs (agents avec compte) — réservée aux ADMINs.

On ne supprime jamais un agent : il pourrait être référencé par des dossiers
existants. La "suppression" est en fait un soft-delete (`actif = False`).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas
from ..database import get_db
from ..services import auth as auth_service
from .auth import utilisateur_admin

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    dependencies=[Depends(utilisateur_admin)],
)


def _valider_role(role: str | None):
    if role is not None and role not in schemas.ROLES:
        raise HTTPException(422, f"role invalide. Valeurs autorisées: {sorted(schemas.ROLES)}")


@router.get("", response_model=list[schemas.AgentOut])
def lister_users(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Agent).order_by(models.Agent.id)))


@router.post("", response_model=schemas.AgentOut, status_code=201)
def creer_user(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    _valider_role(payload.role)
    if db.scalar(select(models.Agent).where(models.Agent.username == payload.username)):
        raise HTTPException(409, "Cet identifiant existe déjà.")
    if db.scalar(select(models.Agent).where(models.Agent.email_pro == payload.email_pro)):
        raise HTTPException(409, "Cet email professionnel existe déjà.")
    agent = models.Agent(
        nom=payload.nom,
        prenom=payload.prenom,
        email_pro=payload.email_pro,
        role=payload.role,
        service=payload.service,
        username=payload.username,
        password_hash=auth_service.hasher_mot_de_passe(payload.password),
        actif=True,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.patch("/{user_id}", response_model=schemas.AgentOut)
def modifier_user(
    user_id: int, payload: schemas.UserUpdate, db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    agent = db.get(models.Agent, user_id)
    if not agent:
        raise HTTPException(404, "Utilisateur introuvable.")
    _valider_role(payload.role)

    if admin.id == agent.id and payload.actif is False:
        raise HTTPException(409, "Impossible de se désactiver soi-même.")
    if admin.id == agent.id and payload.role and payload.role != "ADMIN":
        raise HTTPException(409, "Impossible de retirer son propre rôle ADMIN.")

    for champ, valeur in payload.model_dump(exclude_unset=True).items():
        setattr(agent, champ, valeur)
    db.commit()
    db.refresh(agent)
    return agent


@router.post("/{user_id}/password", status_code=204)
def reset_password(
    user_id: int, payload: schemas.PasswordResetRequest, db: Session = Depends(get_db),
):
    agent = db.get(models.Agent, user_id)
    if not agent:
        raise HTTPException(404, "Utilisateur introuvable.")
    agent.password_hash = auth_service.hasher_mot_de_passe(payload.new_password)
    db.commit()


@router.delete("/{user_id}", status_code=204)
def desactiver_user(
    user_id: int, db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    """Soft-delete : `actif = False`. Le compte conserve son historique."""
    agent = db.get(models.Agent, user_id)
    if not agent:
        raise HTTPException(404, "Utilisateur introuvable.")
    if admin.id == agent.id:
        raise HTTPException(409, "Impossible de se désactiver soi-même.")
    agent.actif = False
    db.commit()
