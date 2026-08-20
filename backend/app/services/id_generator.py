"""Génération d'identifiant réglementaire RECx-AAAAMM-NNNNN (RG007).

L'ID est strictement croissant par mois et n'est jamais recyclé.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from ..config import ENTITE_CODE
from ..models import SequenceCompteur


def generer_code(db: Session, now: datetime | None = None) -> str:
    now = now or datetime.utcnow()
    periode = now.strftime("%Y%m")

    compteur = db.get(SequenceCompteur, periode)
    if compteur is None:
        compteur = SequenceCompteur(periode=periode, dernier_numero=0)
        db.add(compteur)
        db.flush()

    compteur.dernier_numero += 1
    db.flush()

    return f"{ENTITE_CODE}-{periode}-{compteur.dernier_numero:05d}"
