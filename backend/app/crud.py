"""Opérations base de données — appelées par les routes."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import select

from . import models, schemas
from .services import id_generator, sla, audit, communication


def _hash_email(email: str) -> str:
    import hashlib
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


def _trouver_ou_creer_client(db: Session, data: schemas.ClientCreate) -> models.Client:
    if data.email:
        h = _hash_email(data.email)
        existant = db.scalar(select(models.Client).where(models.Client.email_hash == h))
        if existant:
            return existant
        client = models.Client(**data.model_dump(), email_hash=h)
    else:
        client = models.Client(**data.model_dump())
    db.add(client)
    db.flush()
    return client


def creer_reclamation(
    db: Session,
    payload: schemas.ReclamationCreate,
    id_entite: int | None = None,
) -> models.Reclamation:
    import secrets

    client = _trouver_ou_creer_client(db, payload.client)

    now = datetime.utcnow()
    reclamation = models.Reclamation(
        code=id_generator.generer_code(db, now),
        canal=payload.canal,
        statut="NOUVEAU",
        categorie=payload.categorie,
        sous_categorie=payload.sous_categorie,
        priorite=payload.priorite,
        description=payload.description,
        montant_enjeu=payload.montant_enjeu,
        id_client=client.id,
        id_agent_creation=payload.id_agent_creation,
        id_entite=id_entite,
        date_reception=now,
        date_echeance_sla=sla.calculer_echeance(now, payload.priorite),
        token_suivi=secrets.token_urlsafe(32),
    )
    db.add(reclamation)
    db.flush()

    audit.enregistrer(
        db, reclamation.id, "CREATION",
        f"Dossier {reclamation.code} créé via {payload.canal}.",
        auteur=str(payload.id_agent_creation or "système"),
    )
    sujet, corps = communication.template_acr(reclamation, client)
    preuve = communication.envoyer_email(client.email, sujet, corps)
    audit.enregistrer(
        db, reclamation.id, "ACR",
        f"Accusé de réception — email {preuve['statut']} ({preuve.get('driver')}) "
        f"→ {preuve.get('destinataire') or 'sans destinataire'}.",
        auteur="système",
    )
    db.commit()
    db.refresh(reclamation)
    return reclamation


def _construire_filtres(
    statut, priorite, categorie, canal,
    id_equipe_affectee, id_agent_affecte,
    date_debut, date_fin, q,
    id_entite_filtre: int | None = None,
):
    from sqlalchemy import or_
    stmt = select(models.Reclamation).order_by(models.Reclamation.date_reception.desc())
    if id_entite_filtre is not None:
        stmt = stmt.where(models.Reclamation.id_entite == id_entite_filtre)
    if statut:
        stmt = stmt.where(models.Reclamation.statut == statut)
    if priorite:
        stmt = stmt.where(models.Reclamation.priorite == priorite)
    if categorie:
        stmt = stmt.where(models.Reclamation.categorie == categorie)
    if canal:
        stmt = stmt.where(models.Reclamation.canal == canal)
    if id_equipe_affectee is not None:
        stmt = stmt.where(models.Reclamation.id_equipe_affectee == id_equipe_affectee)
    if id_agent_affecte is not None:
        stmt = stmt.where(models.Reclamation.id_agent_affecte == id_agent_affecte)
    if date_debut:
        stmt = stmt.where(models.Reclamation.date_reception >= date_debut)
    if date_fin:
        stmt = stmt.where(models.Reclamation.date_reception <= date_fin)
    if q:
        motif = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            models.Reclamation.code.ilike(motif),
            models.Reclamation.description.ilike(motif),
            models.Reclamation.sous_categorie.ilike(motif),
        ))
    return stmt


def lister(
    db: Session,
    statut: str | None = None,
    priorite: str | None = None,
    categorie: str | None = None,
    canal: str | None = None,
    id_equipe_affectee: int | None = None,
    id_agent_affecte: int | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    q: str | None = None,
    en_alerte: bool = False,
    skip: int = 0,
    limit: int | None = None,
    id_entite_filtre: int | None = None,
) -> tuple[list[models.Reclamation], int]:
    """Retourne (items_paginés, total). Le filtre en_alerte se fait en mémoire."""
    stmt = _construire_filtres(
        statut, priorite, categorie, canal,
        id_equipe_affectee, id_agent_affecte,
        date_debut, date_fin, q,
        id_entite_filtre=id_entite_filtre,
    )
    result = list(db.scalars(stmt))
    if en_alerte:
        now = datetime.utcnow()
        result = [
            r for r in result
            if sla.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
            in {"ALERTE", "ECHU"}
        ]
    total = len(result)
    if limit is not None:
        result = result[skip: skip + limit]
    elif skip:
        result = result[skip:]
    return result, total


def obtenir(db: Session, code: str) -> models.Reclamation | None:
    return db.scalar(select(models.Reclamation).where(models.Reclamation.code == code))


def annoter_sla(reclamation: models.Reclamation, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    pct = sla.pourcentage_consomme(reclamation.date_reception, reclamation.date_echeance_sla, now)
    statut = sla.statut_sla(
        reclamation.date_reception, reclamation.date_echeance_sla, reclamation.statut, now
    )
    return {"sla_pourcentage": round(pct * 100, 1), "sla_statut": statut}
