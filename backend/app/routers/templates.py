"""Bibliothèque de modèles de réponse (FR024).

Création/édition réservées aux admins ; lecture et rendu accessibles à tous
les utilisateurs authentifiés.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas, crud
from ..database import get_db
from .auth import utilisateur_courant, utilisateur_admin

router = APIRouter(
    prefix="/api/templates",
    tags=["templates"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.get("", response_model=list[schemas.ModeleReponseOut])
def lister(categorie: str | None = None, actifs_seuls: bool = True, db: Session = Depends(get_db)):
    stmt = select(models.ModeleReponse).order_by(models.ModeleReponse.libelle)
    if actifs_seuls:
        stmt = stmt.where(models.ModeleReponse.actif == True)
    if categorie:
        from sqlalchemy import or_
        stmt = stmt.where(or_(
            models.ModeleReponse.categorie_cible == categorie,
            models.ModeleReponse.categorie_cible.is_(None),
        ))
    return list(db.scalars(stmt))


@router.post("", response_model=schemas.ModeleReponseOut, status_code=201,
             dependencies=[Depends(utilisateur_admin)])
def creer(payload: schemas.ModeleReponseCreate, db: Session = Depends(get_db)):
    if db.scalar(select(models.ModeleReponse).where(models.ModeleReponse.code == payload.code)):
        raise HTTPException(409, "Code de template déjà utilisé.")
    m = models.ModeleReponse(**payload.model_dump())
    db.add(m)
    db.commit()
    db.refresh(m)
    return m


@router.patch("/{template_id}", response_model=schemas.ModeleReponseOut,
              dependencies=[Depends(utilisateur_admin)])
def modifier(template_id: int, payload: schemas.ModeleReponseCreate,
             db: Session = Depends(get_db)):
    m = db.get(models.ModeleReponse, template_id)
    if not m:
        raise HTTPException(404, "Template introuvable.")
    for k, v in payload.model_dump().items():
        setattr(m, k, v)
    db.commit()
    db.refresh(m)
    return m


@router.delete("/{template_id}", status_code=204,
               dependencies=[Depends(utilisateur_admin)])
def desactiver(template_id: int, db: Session = Depends(get_db)):
    m = db.get(models.ModeleReponse, template_id)
    if not m:
        raise HTTPException(404, "Template introuvable.")
    m.actif = False
    db.commit()


@router.post("/{template_id}/rendre", response_model=schemas.TemplateRenduResponse)
def rendre(template_id: int, payload: schemas.TemplateRenduRequest,
           db: Session = Depends(get_db)):
    """Applique le template sur une réclamation : remplace les variables {client.…}, {reclamation.…}."""
    m = db.get(models.ModeleReponse, template_id)
    if not m:
        raise HTTPException(404, "Template introuvable.")
    r = crud.obtenir(db, payload.code_reclamation)
    if not r:
        raise HTTPException(404, "Réclamation introuvable.")

    def remplacer(texte: str) -> str:
        return (texte
            .replace("{client.nom}", r.client.nom)
            .replace("{client.prenom}", r.client.prenom)
            .replace("{client.email}", r.client.email or "")
            .replace("{reclamation.code}", r.code)
            .replace("{reclamation.categorie}", r.categorie)
            .replace("{reclamation.sous_categorie}", r.sous_categorie or "")
            .replace("{reclamation.priorite}", r.priorite)
            .replace("{reclamation.statut}", r.statut)
            .replace("{reclamation.date_reception}", r.date_reception.strftime("%d/%m/%Y"))
            .replace("{reclamation.date_echeance_sla}", r.date_echeance_sla.strftime("%d/%m/%Y"))
            .replace("{reclamation.montant_enjeu}", f"{r.montant_enjeu:,.0f} FCFA")
        )
    return schemas.TemplateRenduResponse(sujet=remplacer(m.sujet), corps=remplacer(m.corps))
