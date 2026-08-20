"""Endpoints déclenchés par le cron Vercel (ou manuellement par un admin).

Sécurisé par le header Authorization: Bearer <CRON_SECRET>.
Sur Vercel, ce header est injecté automatiquement par la plateforme.
"""
import os
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import sla_escalade

router = APIRouter(prefix="/api/cron", tags=["cron"])


def _verif_secret(authorization: str | None = Header(None)) -> None:
    secret = os.getenv("CRON_SECRET", "").strip()
    if not secret:
        raise HTTPException(500, "CRON_SECRET non configuré sur le serveur.")
    if authorization != f"Bearer {secret}":
        raise HTTPException(401, "Non autorisé.")


@router.get("/sla-check", summary="Escalade + rappels SLA automatiques")
def sla_check(
    db: Session = Depends(get_db),
    _: None = Depends(_verif_secret),
):
    """Déclenché quotidiennement par Vercel Cron (0 7 * * *).

    1. Passe à ALERTE tous les dossiers dont le SLA est consommé à plus de 80%.
    2. Envoie un email de rappel aux agents pour les dossiers à moins de 24h de l'échéance.
    """
    escalades = sla_escalade.escalader_dossiers_en_retard(db)
    rappels = sla_escalade.rappeler_agents_echeance(db)
    return {"escalades": escalades, "rappels": rappels}
