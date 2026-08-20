"""Upload et téléchargement de pièces jointes (FR022)."""
import hashlib
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from .. import models, schemas, crud
from ..database import get_db
from ..config import UPLOAD_DIR, UPLOAD_TAILLE_MAX, UPLOAD_MIME_AUTORISES
from ..services import audit
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api",
    tags=["pieces-jointes"],
    dependencies=[Depends(utilisateur_courant)],
)


@router.post(
    "/reclamations/{code}/pieces-jointes",
    response_model=schemas.PieceJointeOut, status_code=201,
)
def uploader(
    code: str,
    fichier: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")

    if fichier.content_type not in UPLOAD_MIME_AUTORISES:
        raise HTTPException(
            422, f"Type MIME non autorisé : {fichier.content_type}. "
                 f"Autorisés : {sorted(UPLOAD_MIME_AUTORISES)}",
        )

    contenu = fichier.file.read()
    taille = len(contenu)
    if taille == 0:
        raise HTTPException(422, "Fichier vide.")
    if taille > UPLOAD_TAILLE_MAX:
        raise HTTPException(
            413, f"Fichier trop volumineux ({taille} octets, max {UPLOAD_TAILLE_MAX}).",
        )

    checksum = hashlib.sha256(contenu).hexdigest()
    dossier = UPLOAD_DIR / code
    dossier.mkdir(parents=True, exist_ok=True)
    suffixe = Path(fichier.filename or "fichier").suffix[:10]
    chemin = dossier / f"{checksum}{suffixe}"
    if not chemin.exists():
        chemin.write_bytes(contenu)

    pj = models.PieceJointe(
        id_reclamation=reclamation.id,
        nom_fichier=fichier.filename or "fichier",
        type_mime=fichier.content_type,
        taille_octets=taille,
        checksum_sha256=checksum,
        chemin_stockage=str(chemin.relative_to(UPLOAD_DIR.parent)),
        auteur=user.username or f"agent#{user.id}",
    )
    db.add(pj)
    audit.enregistrer(
        db, reclamation.id, "PIECE_JOINTE",
        f"Pièce jointe ajoutée : {pj.nom_fichier} ({taille} o, {fichier.content_type}).",
        auteur=pj.auteur,
    )
    db.commit()
    db.refresh(pj)
    return pj


@router.get("/reclamations/{code}/pieces-jointes", response_model=list[schemas.PieceJointeOut])
def lister(code: str, db: Session = Depends(get_db)):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    from sqlalchemy import select
    return list(db.scalars(
        select(models.PieceJointe)
        .where(models.PieceJointe.id_reclamation == reclamation.id)
        .order_by(models.PieceJointe.date_upload.desc())
    ))


@router.get("/pieces-jointes/{pj_id}/telecharger")
def telecharger(pj_id: int, db: Session = Depends(get_db)):
    pj = db.get(models.PieceJointe, pj_id)
    if not pj:
        raise HTTPException(404, "Pièce jointe introuvable.")
    chemin = UPLOAD_DIR.parent / pj.chemin_stockage
    if not chemin.exists():
        raise HTTPException(404, "Fichier physique introuvable.")
    return FileResponse(
        path=str(chemin),
        media_type=pj.type_mime,
        filename=pj.nom_fichier,
    )
