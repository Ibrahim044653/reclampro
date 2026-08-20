"""Endpoints réclamations : création, lecture, workflow, clôture."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from .. import crud, schemas, models
from ..database import get_db
from ..services import workflow, audit, notification as notif_service, communication
from ..config import SEUIL_VALIDATION_FCFA
from .auth import utilisateur_courant, utilisateur_admin

router = APIRouter(
    prefix="/api/reclamations",
    tags=["reclamations"],
    dependencies=[Depends(utilisateur_courant)],
)


def _valider_enum(valeur: str, ensemble: set[str], champ: str):
    if valeur not in ensemble:
        raise HTTPException(422, f"{champ} invalide. Valeurs autorisées: {sorted(ensemble)}")


@router.post("", response_model=schemas.ReclamationDetail, status_code=201)
def creer(
    payload: schemas.ReclamationCreate,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    _valider_enum(payload.canal, schemas.CANAUX, "canal")
    _valider_enum(payload.categorie, schemas.CATEGORIES, "categorie")
    _valider_enum(payload.priorite, schemas.PRIORITES, "priorite")
    reclamation = crud.creer_reclamation(db, payload, id_entite=user.id_entite)
    sortie = schemas.ReclamationDetail.model_validate(reclamation)
    for k, v in crud.annoter_sla(reclamation).items():
        setattr(sortie, k, v)
    return sortie


@router.post("/suggerer-ia", response_model=schemas.SuggestionIAResponse)
def suggerer_classification(
    payload: schemas.SuggestionIARequest, db: Session = Depends(get_db),
):
    """Suggère catégorie + priorité par classification IA (rule-based + voisinage)."""
    from ..services import classifieur_ia
    res = classifieur_ia.suggerer(db, payload.description)
    return schemas.SuggestionIAResponse(
        categorie_suggeree=res["categorie_suggeree"],
        score_categorie=res["score_categorie"],
        priorite_suggeree=res["priorite_suggeree"],
        score_priorite=res["score_priorite"],
        explication=res["explication"],
        voisins_similaires=[schemas.VoisinIA(**v) for v in res["voisins_similaires"]],
    )


@router.post("/detecter-doublons", response_model=schemas.DetectionDoublonsResponse)
def detecter_doublons(
    payload: schemas.DetectionDoublonsRequest, db: Session = Depends(get_db),
):
    """Appel pré-création : remonte les dossiers potentiellement doublons (FR013)."""
    from ..services import doublons
    items = doublons.detecter(
        db,
        email=payload.email,
        categorie=payload.categorie,
        sous_categorie=payload.sous_categorie,
        description=payload.description,
        jours=payload.jours,
    )
    return schemas.DetectionDoublonsResponse(
        doublons=[schemas.DoublonItem(**it) for it in items],
        nb_potentiels=len(items),
    )


@router.get("/mes", response_model=list[schemas.ReclamationOut])
def mes_reclamations(
    statut_groupe: str | None = Query(None, description="a_traiter / en_cours / traites"),
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    """Réclamations affectées à l'utilisateur courant. Optionnellement filtrées."""
    from ..services import workflow as wf

    stmt = (
        select(models.Reclamation)
        .where(or_(
            models.Reclamation.id_agent_affecte == user.id,
            models.Reclamation.id_agent_creation == user.id,
        ))
        .order_by(models.Reclamation.date_echeance_sla.asc())
    )
    items = list(db.scalars(stmt))
    if statut_groupe == "a_traiter":
        items = [r for r in items if r.statut in wf.STATUTS_A_TRAITER]
    elif statut_groupe == "en_cours":
        items = [r for r in items if r.statut in wf.STATUTS_EN_COURS]
    elif statut_groupe == "traites":
        items = [r for r in items if r.statut in wf.STATUTS_TRAITES]
    return [
        schemas.ReclamationOut.model_validate(r).model_copy(update=crud.annoter_sla(r))
        for r in items
    ]


@router.get("/mon-bilan")
def mon_bilan(
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    """Compteurs personnels de l'utilisateur courant."""
    from ..services import workflow as wf
    from ..services import sla as sla_service

    items = list(db.scalars(
        select(models.Reclamation).where(or_(
            models.Reclamation.id_agent_affecte == user.id,
            models.Reclamation.id_agent_creation == user.id,
        ))
    ))
    now = datetime.utcnow()
    a_traiter = sum(1 for r in items if r.statut in wf.STATUTS_A_TRAITER)
    en_cours = sum(1 for r in items if r.statut in wf.STATUTS_EN_COURS)
    traites = sum(1 for r in items if r.statut in wf.STATUTS_TRAITES)
    en_alerte = sum(
        1 for r in items
        if r.statut not in wf.STATUTS_TRAITES
        and sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        in {"ALERTE", "ECHU"}
    )
    return {
        "a_traiter": a_traiter,
        "en_cours": en_cours,
        "traites": traites,
        "total": len(items),
        "en_alerte_sla": en_alerte,
        "agent": {
            "id": user.id, "username": user.username,
            "nom_complet": f"{user.prenom} {user.nom}",
            "role": user.role,
            "equipe": user.equipe.libelle if user.equipe else None,
        },
    }


@router.get("", response_model=list[schemas.ReclamationOut])
def lister(
    response: "Response",
    statut: str | None = None,
    priorite: str | None = None,
    categorie: str | None = None,
    canal: str | None = None,
    id_equipe_affectee: int | None = None,
    id_agent_affecte: int | None = None,
    date_debut: datetime | None = None,
    date_fin: datetime | None = None,
    q: str | None = Query(None, description="Recherche dans code/description/sous-catégorie"),
    en_alerte: bool = Query(False),
    skip: int = Query(0, ge=0, description="Pagination — offset"),
    limit: int | None = Query(None, ge=1, le=500, description="Pagination — nombre max d'items"),
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    # Isolation multi-entité (BR009) : non-admin = restreint à son entité
    id_entite_filtre = None if user.role == "ADMIN" else user.id_entite
    items, total = crud.lister(
        db,
        statut=statut, priorite=priorite, categorie=categorie, canal=canal,
        id_equipe_affectee=id_equipe_affectee, id_agent_affecte=id_agent_affecte,
        date_debut=date_debut, date_fin=date_fin, q=q, en_alerte=en_alerte,
        skip=skip, limit=limit, id_entite_filtre=id_entite_filtre,
    )
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page-Skip"] = str(skip)
    response.headers["X-Page-Limit"] = str(limit if limit is not None else total)
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count, X-Page-Skip, X-Page-Limit"
    return [
        schemas.ReclamationOut.model_validate(r).model_copy(update=crud.annoter_sla(r))
        for r in items
    ]


@router.get("/{code}", response_model=schemas.ReclamationDetail)
def detail(
    code: str,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    # Isolation multi-entité (BR009) : un agent d'une autre entité reçoit un 404 (pas un 403,
    # pour ne pas révéler l'existence du dossier).
    if user.role != "ADMIN" and reclamation.id_entite is not None \
       and user.id_entite is not None and reclamation.id_entite != user.id_entite:
        raise HTTPException(404, "Réclamation introuvable")
    sortie = schemas.ReclamationDetail.model_validate(reclamation)
    for k, v in crud.annoter_sla(reclamation).items():
        setattr(sortie, k, v)
    return sortie


@router.post("/{code}/statut", response_model=schemas.ReclamationDetail)
def changer_statut(
    code: str, payload: schemas.ChangeStatutRequest, db: Session = Depends(get_db)
):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    _valider_enum(payload.nouveau_statut, schemas.STATUTS, "nouveau_statut")
    if not workflow.transition_autorisee(reclamation.statut, payload.nouveau_statut):
        raise HTTPException(
            409,
            f"Transition {reclamation.statut} → {payload.nouveau_statut} non autorisée. "
            f"Statuts possibles: {workflow.statuts_suivants_possibles(reclamation.statut)}",
        )
    ancien = reclamation.statut
    reclamation.statut = payload.nouveau_statut
    audit.enregistrer(
        db, reclamation.id, "CHANGEMENT_STATUT",
        payload.commentaire or f"Statut changé.",
        auteur=payload.auteur, valeur_avant=ancien, valeur_apres=payload.nouveau_statut,
    )
    db.commit()
    db.refresh(reclamation)
    return schemas.ReclamationDetail.model_validate(reclamation).model_copy(
        update=crud.annoter_sla(reclamation)
    )


@router.post("/{code}/affectation", response_model=schemas.ReclamationDetail)
def affecter(
    code: str,
    payload: schemas.AffectationRequest,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    agent = db.get(models.Agent, payload.id_agent_affecte)
    if not agent:
        raise HTTPException(404, "Agent introuvable")

    ancien = str(reclamation.id_agent_affecte)
    reclamation.id_agent_affecte = agent.id
    if agent.id_equipe and reclamation.id_equipe_affectee != agent.id_equipe:
        reclamation.id_equipe_affectee = agent.id_equipe
    if reclamation.statut in {"NOUVEAU", "QUALIF"}:
        reclamation.statut = "AFFECTE"

    audit.enregistrer(
        db, reclamation.id, "AFFECTATION",
        f"Dossier affecté à {agent.prenom} {agent.nom}.",
        auteur=payload.auteur, valeur_avant=ancien, valeur_apres=str(agent.id),
    )

    if agent.id != user.id:
        notif_service.notifier_agent(
            db, agent.id, "AFFECTATION",
            f"Le dossier {reclamation.code} vous a été affecté.",
            reclamation=reclamation,
        )

    db.commit()
    db.refresh(reclamation)
    return schemas.ReclamationDetail.model_validate(reclamation).model_copy(
        update=crud.annoter_sla(reclamation)
    )


@router.post("/{code}/transfert", response_model=schemas.ReclamationDetail)
def transferer(
    code: str,
    payload: schemas.TransfertEquipeRequest,
    db: Session = Depends(get_db),
    user: models.Agent = Depends(utilisateur_courant),
):
    """Transfère le dossier à une autre équipe et notifie tous ses membres actifs."""
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")

    equipe_cible = db.get(models.Equipe, payload.id_equipe_cible)
    if not equipe_cible:
        raise HTTPException(404, "Équipe cible introuvable")

    if reclamation.id_equipe_affectee == equipe_cible.id:
        raise HTTPException(409, "Le dossier est déjà affecté à cette équipe.")

    ancien_id = str(reclamation.id_equipe_affectee or "")
    reclamation.id_equipe_affectee = equipe_cible.id
    reclamation.id_agent_affecte = None  # remise dans le pool de la nouvelle équipe
    if reclamation.statut in {"NOUVEAU", "QUALIF"}:
        reclamation.statut = "AFFECTE"

    audit.enregistrer(
        db, reclamation.id, "TRANSFERT_EQUIPE",
        f"Dossier transféré à l'équipe '{equipe_cible.libelle}'. Motif : {payload.motif}",
        auteur=payload.auteur, valeur_avant=ancien_id, valeur_apres=str(equipe_cible.id),
    )

    nb = notif_service.notifier_equipe(
        db, equipe_cible.id, "TRANSFERT",
        f"Nouveau dossier {reclamation.code} transféré à votre équipe — {payload.motif}",
        reclamation=reclamation,
        exclus={user.id},
    )
    audit.enregistrer(
        db, reclamation.id, "NOTIFICATION",
        f"{nb} membre(s) de l'équipe '{equipe_cible.libelle}' notifié(s).",
        auteur="système",
    )

    db.commit()
    db.refresh(reclamation)
    return schemas.ReclamationDetail.model_validate(reclamation).model_copy(
        update=crud.annoter_sla(reclamation)
    )


@router.post("/{code}/commentaire", response_model=schemas.InteractionOut)
def commenter(code: str, payload: schemas.CommentaireRequest, db: Session = Depends(get_db)):
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    inter = audit.enregistrer(
        db, reclamation.id, "COMMENTAIRE", payload.contenu, auteur=payload.auteur,
    )
    db.commit()
    db.refresh(inter)
    return inter


@router.post("/{code}/cloture", response_model=schemas.ReclamationDetail)
def cloturer(
    code: str,
    payload: schemas.ClotureRequest,
    db: Session = Depends(get_db),
    _admin: models.Agent = Depends(utilisateur_admin),
):
    """Clôture avec motif obligatoire (FR040 + RG008). Réservée aux admins."""
    reclamation = crud.obtenir(db, code)
    if not reclamation:
        raise HTTPException(404, "Réclamation introuvable")
    _valider_enum(payload.motif, schemas.MOTIFS_CLOTURE, "motif")

    if reclamation.statut == "CLOTURE":
        raise HTTPException(409, "Dossier déjà clôturé.")

    if reclamation.montant_enjeu > SEUIL_VALIDATION_FCFA and reclamation.statut != "VALIDATION":
        raise HTTPException(
            409,
            f"Montant > {SEUIL_VALIDATION_FCFA:,} FCFA — validation hiérarchique requise (RG009).",
        )

    from datetime import datetime
    ancien = reclamation.statut
    reclamation.statut = "CLOTURE"
    reclamation.motif_cloture = payload.motif
    reclamation.date_cloture = datetime.utcnow()

    audit.enregistrer(
        db, reclamation.id, "CLOTURE",
        payload.commentaire or f"Clôture — motif: {payload.motif}.",
        auteur=payload.auteur, valeur_avant=ancien, valeur_apres="CLOTURE",
    )
    sujet, corps = communication.template_cloture(reclamation, reclamation.client)
    preuve = communication.envoyer_email(reclamation.client.email, sujet, corps)
    audit.enregistrer(
        db, reclamation.id, "NOTIFICATION",
        f"Notification clôture — email {preuve['statut']} ({preuve.get('driver')}) "
        f"→ {preuve.get('destinataire') or 'sans destinataire'}.",
        auteur="système",
    )
    db.commit()
    db.refresh(reclamation)
    return schemas.ReclamationDetail.model_validate(reclamation).model_copy(
        update=crud.annoter_sla(reclamation)
    )
