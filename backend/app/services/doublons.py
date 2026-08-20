"""Détection de doublons potentiels (FR013).

Heuristique simple :
- Même email client (via hash) → +0.5 au score
- Même catégorie / sous-catégorie → +0.2 chacun
- Similarité du texte (Jaccard sur mots) >= 0.5 → +0.2

Score >= 0.5 = signalé comme doublon potentiel. Décision finale humaine.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models
from ..crud import _hash_email


def _tokens(texte: str) -> set[str]:
    if not texte:
        return set()
    return {m.lower() for m in texte.split() if len(m) >= 4}


def _similarite(a: str | None, b: str | None) -> float:
    ta, tb = _tokens(a or ""), _tokens(b or "")
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


def detecter(
    db: Session,
    email: str | None,
    categorie: str | None,
    sous_categorie: str | None,
    description: str | None,
    jours: int = 7,
) -> list[dict]:
    """Retourne la liste des dossiers potentiellement doublons avec score."""
    if not (email or sous_categorie or description):
        return []

    seuil_date = datetime.utcnow() - timedelta(days=jours)
    stmt = (
        select(models.Reclamation)
        .where(models.Reclamation.date_reception >= seuil_date)
        .order_by(models.Reclamation.date_reception.desc())
    )

    candidats = list(db.scalars(stmt))
    if email:
        h = _hash_email(email)
        # On préfère filtrer mais on garde aussi les autres pour la similarité texte
    else:
        h = None

    resultats = []
    for r in candidats:
        score = 0.0
        if h and r.client and r.client.email_hash == h:
            score += 0.5
        if categorie and r.categorie == categorie:
            score += 0.2
        if sous_categorie and r.sous_categorie == sous_categorie:
            score += 0.2
        if description and _similarite(description, r.description) >= 0.5:
            score += 0.2
        if score >= 0.5:
            resultats.append({
                "code": r.code,
                "statut": r.statut,
                "categorie": r.categorie,
                "sous_categorie": r.sous_categorie,
                "date_reception": r.date_reception,
                "score_similarite": round(min(1.0, score), 2),
            })
    resultats.sort(key=lambda x: x["score_similarite"], reverse=True)
    return resultats[:5]
