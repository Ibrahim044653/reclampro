"""Webhook WhatsApp Business + endpoint d'envoi (FR003).

Le webhook est public (l'API Meta doit pouvoir y accéder) mais protégé par
un verify_token configuré côté Meta.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from .. import models, schemas, crud, config
from ..database import get_db
from ..services import whatsapp, audit, classifieur_ia
from .auth import utilisateur_courant

router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])
logger = logging.getLogger("whatsapp_router")


# --- Webhook Meta (public) ---

@router.get("/webhook", response_class=PlainTextResponse)
def verifier_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
):
    """Handshake initial de Meta : on doit renvoyer le challenge si le token matche."""
    if hub_mode == "subscribe" and hub_verify_token == config.WHATSAPP_VERIFY_TOKEN:
        return hub_challenge or "ok"
    raise HTTPException(403, "Verify token invalide.")


@router.post("/webhook")
async def recevoir_webhook(request: Request, db: Session = Depends(get_db)):
    """Reçoit un message WhatsApp et crée automatiquement un dossier."""
    payload = await request.json()
    msg = whatsapp.parser_message_entrant(payload)
    if not msg:
        return {"statut": "IGNORE", "raison": "Pas de message texte exploitable"}

    # Classification IA pour pré-remplir catégorie + priorité
    suggestion = classifieur_ia.suggerer(db, msg["texte"])

    nom_complet = (msg.get("nom_profil") or msg["from"]).split()
    prenom = nom_complet[0] if nom_complet else "Client"
    nom = " ".join(nom_complet[1:]) if len(nom_complet) > 1 else "WhatsApp"

    payload_creation = schemas.ReclamationCreate(
        canal="WHATSAPP",
        categorie=suggestion["categorie_suggeree"],
        sous_categorie=None,
        priorite=suggestion["priorite_suggeree"],
        description=msg["texte"][:5000],
        montant_enjeu=0,
        client=schemas.ClientCreate(
            nom=nom, prenom=prenom,
            email=None, telephone=msg["from"],
        ),
    )
    r = crud.creer_reclamation(db, payload_creation)
    audit.enregistrer(
        db, r.id, "CLASSIFICATION_IA",
        f"Catégorie/priorité suggérées par IA : {suggestion['categorie_suggeree']} / "
        f"{suggestion['priorite_suggeree']}. {suggestion['explication']}",
        auteur="système",
    )

    # Accusé via WhatsApp si Cloud configuré
    preuve = whatsapp.envoyer_message(
        msg["from"],
        f"Bonjour, nous avons bien reçu votre message. "
        f"Référence dossier : {r.code}. Notre équipe vous contactera rapidement.",
    )
    audit.enregistrer(
        db, r.id, "ACR_WHATSAPP",
        f"Accusé WhatsApp {preuve['statut']} → {msg['from']}",
        auteur="système",
    )
    db.commit()
    return {"statut": "OK", "code_reclamation": r.code}


# --- Envoi manuel par un agent (authentifié) ---

from pydantic import BaseModel


class EnvoyerWhatsAppRequest(BaseModel):
    code_reclamation: str
    message: str


@router.post("/envoyer")
def envoyer(
    payload: EnvoyerWhatsAppRequest,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    """Envoi manuel WhatsApp au client (utilisé depuis la page détail)."""
    r = crud.obtenir(db, payload.code_reclamation)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")
    if not r.client or not r.client.telephone:
        raise HTTPException(409, "Client sans numéro WhatsApp.")
    preuve = whatsapp.envoyer_message(r.client.telephone, payload.message)
    audit.enregistrer(
        db, r.id, "WHATSAPP_SORTANT",
        f"Message WhatsApp envoyé : {preuve['statut']} → {r.client.telephone}",
        auteur=user.username or f"agent#{user.id}",
    )
    db.commit()
    return preuve
