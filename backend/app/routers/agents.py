"""Liste des agents — pour les selects du frontend."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas
from ..database import get_db
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api/agents",
    tags=["agents"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.get("", response_model=list[schemas.AgentOut])
def lister(db: Session = Depends(get_db)):
    return list(db.scalars(select(models.Agent).where(models.Agent.actif == True)))
