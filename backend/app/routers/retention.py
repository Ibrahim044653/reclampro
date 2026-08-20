"""Endpoints admin pour la politique de rétention (RG011 + RGPD)."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, crud
from ..database import get_db
from ..services import retention, audit
from .auth import utilisateur_admin

router = APIRouter(prefix="/api/admin/retention", tags=["admin-retention"])


@router.get("/candidats")
def candidats(
    db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    """Liste les dossiers éligibles à l'archivage ou à l'anonymisation."""
    archives = retention.candidats_archivage(db)
    anonymises = retention.candidats_anonymisation(db)
    return {
        "archivage_5ans": [r.code for r in archives],
        "anonymisation_10ans": [r.code for r in anonymises],
        "nb_archivage": len(archives),
        "nb_anonymisation": len(anonymises),
    }


@router.post("/appliquer")
def appliquer(
    db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    """Lance la politique de rétention (archivage J+5 ans, anonymisation J+10 ans)."""
    return retention.appliquer_retention(db)


@router.post("/{code}/anonymiser-rgpd", status_code=204)
def anonymiser_rgpd(
    code: str,
    db: Session = Depends(get_db),
    admin: models.Agent = Depends(utilisateur_admin),
):
    """Droit à l'effacement RGPD — anonymisation à la demande du client."""
    r = crud.obtenir(db, code)
    if not r:
        raise HTTPException(404, "Réclamation introuvable")
    if r.anonymisee:
        raise HTTPException(409, "Dossier déjà anonymisé.")
    audit.enregistrer(
        db, r.id, "ANONYMISATION_RGPD",
        f"Anonymisation à la demande du client (RGPD) par {admin.prenom} {admin.nom}.",
        auteur=admin.username or f"agent#{admin.id}",
    )
    retention.anonymiser_a_la_demande(db, r)
