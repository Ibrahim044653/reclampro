"""Notifications de l'utilisateur connecté."""
import asyncio
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from .. import models, schemas
from ..database import get_db, SessionLocal
from ..services import auth as auth_service
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api/notifications",
    tags=["notifications"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.get("", response_model=list[schemas.NotificationOut])
def mes_notifications(
    non_lues_seulement: bool = False,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    stmt = (
        select(models.Notification)
        .where(models.Notification.id_destinataire == user.id)
        .order_by(models.Notification.date_creation.desc())
        .limit(limit)
    )
    if non_lues_seulement:
        stmt = stmt.where(models.Notification.lue == False)
    return list(db.scalars(stmt))


@router.get("/count")
def compteur_non_lues(
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    n = db.scalar(
        select(models.Notification)
        .where(models.Notification.id_destinataire == user.id, models.Notification.lue == False)
        .with_only_columns(models.Notification.id)
    )
    from sqlalchemy import func
    count = db.scalar(
        select(func.count(models.Notification.id))
        .where(models.Notification.id_destinataire == user.id, models.Notification.lue == False)
    ) or 0
    return {"non_lues": count}


@router.post("/{notif_id}/lue", status_code=204)
def marquer_lue(
    notif_id: int,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    n = db.get(models.Notification, notif_id)
    if not n or n.id_destinataire != user.id:
        raise HTTPException(404, "Notification introuvable.")
    n.lue = True
    db.commit()


@router.get("/stream")
async def stream_notifications(
    token: str = Query(..., description="JWT (passé en query car EventSource ne gère pas les headers)"),
):
    """Server-Sent Events : flux temps réel des notifications.

    EventSource côté navigateur ne permet pas d'envoyer un header
    Authorization, donc le token JWT est passé en query string.
    """
    payload = auth_service.decoder_token(token)
    if not payload:
        raise HTTPException(401, "Token invalide")
    user_id = int(payload["sub"])

    async def event_stream():
        last_id = 0
        # On envoie d'abord le compteur initial
        with SessionLocal() as db:
            from sqlalchemy import func
            count = db.scalar(
                select(func.count(models.Notification.id))
                .where(models.Notification.id_destinataire == user_id,
                       models.Notification.lue == False)
            ) or 0
            yield f"event: count\ndata: {json.dumps({'non_lues': count})}\n\n"
            dernier = db.scalar(
                select(func.max(models.Notification.id))
                .where(models.Notification.id_destinataire == user_id)
            )
            last_id = dernier or 0

        while True:
            await asyncio.sleep(5)
            with SessionLocal() as db:
                nouvelles = list(db.scalars(
                    select(models.Notification)
                    .where(models.Notification.id_destinataire == user_id,
                           models.Notification.id > last_id)
                    .order_by(models.Notification.id)
                ))
                if nouvelles:
                    for n in nouvelles:
                        last_id = max(last_id, n.id)
                        data = {
                            "id": n.id, "type": n.type, "contenu": n.contenu,
                            "code_reclamation": n.code_reclamation,
                            "date_creation": n.date_creation.isoformat(),
                        }
                        yield f"event: notification\ndata: {json.dumps(data)}\n\n"

                from sqlalchemy import func
                count = db.scalar(
                    select(func.count(models.Notification.id))
                    .where(models.Notification.id_destinataire == user_id,
                           models.Notification.lue == False)
                ) or 0
                yield f"event: count\ndata: {json.dumps({'non_lues': count})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/toutes-lues", status_code=204)
def tout_marquer_lu(
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    db.execute(
        update(models.Notification)
        .where(models.Notification.id_destinataire == user.id, models.Notification.lue == False)
        .values(lue=True)
    )
    db.commit()
