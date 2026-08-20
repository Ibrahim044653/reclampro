"""Endpoint admin pour déclencher manuellement la capture IMAP."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import imap_capture
from .. import models
from .auth import utilisateur_admin

router = APIRouter(prefix="/api/admin", tags=["admin-imap"])


@router.post("/imap/traiter")
def declencher_traitement(
    marquer_lus: bool = True,
    db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    """Connecte à la boîte IMAP configurée et crée un dossier par email non lu."""
    return imap_capture.traiter_boite(db, marquer_lus=marquer_lus)
