"""Liste et détail des équipes (utilisé pour les selects + page reportings)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas
from ..database import get_db
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api/equipes",
    tags=["equipes"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.get("", response_model=list[schemas.EquipeOut])
def lister(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Equipe).order_by(models.Equipe.libelle)))


@router.get("/{equipe_id}/membres", response_model=list[schemas.AgentOut])
def membres(equipe_id: int, db: Session = Depends(get_db)):
    eq = db.get(models.Equipe, equipe_id)
    if not eq:
        raise HTTPException(404, "Équipe introuvable")
    return [a for a in eq.membres if a.actif]
