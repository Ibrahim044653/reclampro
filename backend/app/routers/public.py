"""Portail client public (FR004 + FR033) — sans authentification.

- POST /api/public/reclamations         : soumission directe par un client
- GET  /api/public/reclamations/{token} : suivi via token opaque
- GET  /api/public/recherche            : retrouver son dossier par email + code

Aucun de ces endpoints n'expose les données sensibles d'un autre client :
le token sert de capability — connaître le token = avoir accès au dossier.
Pour la recherche email+code : on vérifie que l'email est bien celui du client
qui a ouvert le dossier avant de retourner les informations.
"""
import hashlib
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from pydantic import BaseModel

from .. import crud, schemas, models
from ..database import get_db

router = APIRouter(prefix="/api/public", tags=["public"])


class PublicSubmissionResponse(BaseModel):
    code: str
    token_suivi: str
    statut: str
    date_reception: datetime
    url_suivi: str


@router.post("/reclamations", response_model=PublicSubmissionResponse, status_code=201)
def soumettre(payload: schemas.ReclamationCreate, db: Session = Depends(get_db)):
    """Soumission publique. Force le canal à WEB pour traçabilité."""
    payload.canal = "WEB"
    payload.id_agent_creation = None
    if payload.categorie not in schemas.CATEGORIES:
        raise HTTPException(422, "Catégorie invalide.")
    if payload.priorite not in schemas.PRIORITES:
        raise HTTPException(422, "Priorité invalide.")
    reclamation = crud.creer_reclamation(db, payload)
    return PublicSubmissionResponse(
        code=reclamation.code,
        token_suivi=reclamation.token_suivi,
        statut=reclamation.statut,
        date_reception=reclamation.date_reception,
        url_suivi=f"/portail-suivi.html?token={reclamation.token_suivi}",
    )


class PublicSuiviInteraction(BaseModel):
    type: str
    contenu: str
    date_heure: datetime


class PublicSuiviResponse(BaseModel):
    code: str
    statut: str
    statut_libelle: str
    priorite: str
    categorie: str
    sous_categorie: str | None
    date_reception: datetime
    date_echeance_sla: datetime
    date_cloture: datetime | None
    motif_cloture: str | None
    interactions_publiques: list[PublicSuiviInteraction]


STATUTS_LIBELLES = {
    "NOUVEAU": "Reçu",
    "QUALIF": "En qualification",
    "AFFECTE": "Pris en charge",
    "EN_COURS": "En traitement",
    "ATT_CLIENT": "En attente d'informations de votre part",
    "ALERTE": "En traitement",
    "ESCALADE": "En traitement (escaladé)",
    "VALIDATION": "En validation finale",
    "DECISION": "Décision rendue",
    "CLOTURE": "Clôturé",
    "REJETE": "Non recevable",
    "REOUVRE": "Réouvert",
}

# Types d'interactions visibles côté client (on cache l'audit interne).
TYPES_VISIBLES = {"CREATION", "ACR", "CHANGEMENT_STATUT", "NOTIFICATION", "CLOTURE"}


def _construire_reponse_suivi(reclamation: models.Reclamation) -> PublicSuiviResponse:
    interactions = [
        PublicSuiviInteraction(
            type=i.type, contenu=i.contenu, date_heure=i.date_heure,
        )
        for i in reclamation.interactions
        if i.type in TYPES_VISIBLES
    ]
    return PublicSuiviResponse(
        code=reclamation.code,
        statut=reclamation.statut,
        statut_libelle=STATUTS_LIBELLES.get(reclamation.statut, reclamation.statut),
        priorite=reclamation.priorite,
        categorie=reclamation.categorie,
        sous_categorie=reclamation.sous_categorie,
        date_reception=reclamation.date_reception,
        date_echeance_sla=reclamation.date_echeance_sla,
        date_cloture=reclamation.date_cloture,
        motif_cloture=reclamation.motif_cloture,
        interactions_publiques=interactions,
    )


@router.get("/reclamations/{token}", response_model=PublicSuiviResponse)
def suivre(token: str, db: Session = Depends(get_db)):
    if not token or len(token) < 20:
        raise HTTPException(404, "Token invalide.")
    reclamation = db.scalar(
        select(models.Reclamation).where(models.Reclamation.token_suivi == token)
    )
    if not reclamation:
        raise HTTPException(404, "Dossier introuvable ou lien expiré.")
    return _construire_reponse_suivi(reclamation)


@router.get("/recherche", response_model=PublicSuiviResponse)
def rechercher_par_email_et_code(
    email: str = Query(..., description="Adresse email fournie lors de la soumission"),
    code: str = Query(..., description="Numéro de dossier (ex. RECB-202508-00001)"),
    db: Session = Depends(get_db),
):
    """Retrouver un dossier sans token, par email + numéro de dossier.

    Vérifie que l'email est bien celui du client titulaire du dossier
    pour éviter toute fuite d'information.
    """
    email_hash = hashlib.sha256(email.strip().lower().encode()).hexdigest()
    client = db.scalar(select(models.Client).where(models.Client.email_hash == email_hash))
    if not client:
        raise HTTPException(404, "Aucun compte trouvé avec cette adresse email.")
    reclamation = db.scalar(
        select(models.Reclamation).where(
            models.Reclamation.code == code.strip().upper(),
            models.Reclamation.id_client == client.id,
        )
    )
    if not reclamation:
        raise HTTPException(
            404,
            "Dossier introuvable. Vérifiez l'adresse email et le numéro de dossier.",
        )
    return _construire_reponse_suivi(reclamation)
