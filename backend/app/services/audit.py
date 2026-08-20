"""Enregistrement d'une interaction au journal immuable (BR002, FR021)."""
from sqlalchemy.orm import Session

from ..models import Interaction


def enregistrer(
    db: Session,
    id_reclamation: int,
    type_action: str,
    contenu: str,
    auteur: str = "système",
    valeur_avant: str | None = None,
    valeur_apres: str | None = None,
) -> Interaction:
    interaction = Interaction(
        id_reclamation=id_reclamation,
        type=type_action,
        contenu=contenu,
        auteur=auteur,
        valeur_avant=valeur_avant,
        valeur_apres=valeur_apres,
    )
    db.add(interaction)
    db.flush()
    return interaction
