"""Reportings de pilotage — réservé aux admins.

Endpoints d'agrégation paramétrables par période (semaine/mois/trimestre/année)
et par dimension (catégorie, priorité, canal, équipe, statut).
"""
from datetime import datetime, timedelta, date
from collections import Counter, defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models, schemas
from ..database import get_db
from ..services import sla as sla_service, workflow as wf
from .auth import utilisateur_admin

router = APIRouter(
    prefix="/api/reports",
    tags=["reports"],
    dependencies=[Depends(utilisateur_admin)],
)

DIMENSIONS = {"categorie", "sous_categorie", "priorite", "canal", "statut", "equipe", "agent"}
PERIODES = {"semaine", "mois", "trimestre", "annee"}


def _bornes_periode(periode: str, date_ref: datetime) -> tuple[datetime, datetime]:
    if periode == "semaine":
        debut = date_ref - timedelta(days=date_ref.weekday())
        debut = debut.replace(hour=0, minute=0, second=0, microsecond=0)
        fin = debut + timedelta(days=7)
    elif periode == "mois":
        debut = date_ref.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        next_month_day = (debut + timedelta(days=32)).replace(day=1)
        fin = next_month_day
    elif periode == "trimestre":
        m0 = ((date_ref.month - 1) // 3) * 3 + 1
        debut = date_ref.replace(month=m0, day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = (debut + timedelta(days=95)).replace(day=1)
    elif periode == "annee":
        debut = date_ref.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = debut.replace(year=debut.year + 1)
    else:
        raise HTTPException(422, f"periode invalide. Valeurs: {sorted(PERIODES)}")
    return debut, fin


def _cle_dimension(r: models.Reclamation, dim: str) -> str:
    if dim == "equipe":
        return r.equipe_affectee.libelle if r.equipe_affectee else "Non affectée"
    if dim == "agent":
        return f"{r.agent_affecte.prenom} {r.agent_affecte.nom}" if r.agent_affecte else "Non assigné"
    return getattr(r, dim) or "—"


@router.get("/synthese")
def synthese(
    periode: str = Query("mois"),
    date_ref: datetime | None = None,
    db: Session = Depends(get_db),
):
    """Vue d'ensemble sur une période donnée : volumes + conformité SLA + délais moyens."""
    date_ref = date_ref or datetime.utcnow()
    debut, fin = _bornes_periode(periode, date_ref)

    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    cloturees = [r for r in toutes if r.statut == "CLOTURE"]
    en_cours = [r for r in toutes if r.statut not in {"CLOTURE", "REJETE"}]

    delais = [
        (r.date_cloture - r.date_reception).total_seconds() / 3600
        for r in cloturees if r.date_cloture
    ]
    delai_moyen_h = round(sum(delais) / len(delais), 1) if delais else 0.0

    now = datetime.utcnow()
    statut_sla = lambda r: sla_service.statut_sla(
        r.date_reception, r.date_echeance_sla, r.statut, now
    )
    repartition_sla = Counter(statut_sla(r) for r in toutes)

    actifs = repartition_sla.get("OK", 0) + repartition_sla.get("ALERTE", 0) + repartition_sla.get("ECHU", 0)
    taux_conformite = round(repartition_sla.get("OK", 0) / actifs * 100, 1) if actifs else 0.0

    motifs_cloture = Counter(r.motif_cloture for r in cloturees if r.motif_cloture)

    return {
        "periode": periode,
        "date_debut": debut.isoformat(),
        "date_fin": fin.isoformat(),
        "total_recues": len(toutes),
        "total_cloturees": len(cloturees),
        "total_en_cours": len(en_cours),
        "delai_moyen_traitement_heures": delai_moyen_h,
        "taux_conformite_sla": taux_conformite,
        "repartition_sla": [{"label": k, "valeur": v} for k, v in repartition_sla.items()],
        "repartition_motif_cloture": [{"label": k, "valeur": v} for k, v in motifs_cloture.most_common()],
    }


@router.get("/par-dimension")
def par_dimension(
    dim: str = Query(..., description=f"Dimension d'agrégation : {sorted(DIMENSIONS)}"),
    periode: str = Query("mois"),
    date_ref: datetime | None = None,
    db: Session = Depends(get_db),
):
    """Répartition + taux de conformité SLA sur chaque modalité de la dimension."""
    if dim not in DIMENSIONS:
        raise HTTPException(422, f"dim invalide. Valeurs: {sorted(DIMENSIONS)}")
    date_ref = date_ref or datetime.utcnow()
    debut, fin = _bornes_periode(periode, date_ref)

    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    now = datetime.utcnow()

    par_cle: dict[str, dict] = defaultdict(
        lambda: {"recues": 0, "cloturees": 0, "ok_sla": 0, "actifs": 0}
    )
    for r in toutes:
        cle = _cle_dimension(r, dim)
        d = par_cle[cle]
        d["recues"] += 1
        if r.statut == "CLOTURE":
            d["cloturees"] += 1
        s = sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        if s in {"OK", "ALERTE", "ECHU"}:
            d["actifs"] += 1
            if s == "OK":
                d["ok_sla"] += 1

    items = []
    for cle, d in par_cle.items():
        items.append({
            "modalite": cle,
            "recues": d["recues"],
            "cloturees": d["cloturees"],
            "taux_cloture_pct": round(d["cloturees"] / d["recues"] * 100, 1) if d["recues"] else 0.0,
            "taux_conformite_sla_pct": round(d["ok_sla"] / d["actifs"] * 100, 1) if d["actifs"] else 0.0,
        })
    items.sort(key=lambda x: x["recues"], reverse=True)
    return {
        "dimension": dim,
        "periode": periode,
        "date_debut": debut.isoformat(),
        "date_fin": fin.isoformat(),
        "items": items,
    }


@router.get("/serie-temporelle")
def serie_temporelle(
    granularite: str = Query("mois", description="jour, semaine, mois ou annee"),
    points: int = Query(12, ge=1, le=60, description="Nombre de points dans la série"),
    db: Session = Depends(get_db),
):
    """Série historique reçues vs clôturées, sur N derniers buckets."""
    if granularite not in {"jour", "semaine", "mois", "annee"}:
        raise HTTPException(422, "granularité invalide.")

    now = datetime.utcnow()
    toutes = list(db.scalars(select(models.Reclamation)))

    def cle_bucket(d: datetime) -> tuple[str, datetime, datetime]:
        if granularite == "jour":
            debut = d.replace(hour=0, minute=0, second=0, microsecond=0)
            return debut.strftime("%d/%m"), debut, debut + timedelta(days=1)
        if granularite == "semaine":
            debut = (d - timedelta(days=d.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
            return f"S{debut.isocalendar().week}", debut, debut + timedelta(days=7)
        if granularite == "mois":
            mois_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jui", "Aoû", "Sep", "Oct", "Nov", "Déc"]
            debut = d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            fin = (debut + timedelta(days=32)).replace(day=1)
            return f"{mois_labels[debut.month - 1]} {debut.year % 100:02d}", debut, fin
        debut = d.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        fin = debut.replace(year=debut.year + 1)
        return str(debut.year), debut, fin

    buckets = []
    cursor = now
    for _ in range(points):
        label, debut, fin = cle_bucket(cursor)
        items_b = [r for r in toutes if debut <= r.date_reception < fin]
        cloturees_b = [r for r in toutes if r.date_cloture and debut <= r.date_cloture < fin]
        buckets.append({
            "label": label,
            "debut": debut.isoformat(),
            "recues": len(items_b),
            "cloturees": len(cloturees_b),
        })
        # reculer d'un bucket
        if granularite == "jour":
            cursor = cursor - timedelta(days=1)
        elif granularite == "semaine":
            cursor = cursor - timedelta(days=7)
        elif granularite == "mois":
            cursor = (cursor.replace(day=1) - timedelta(days=1))
        else:
            cursor = cursor.replace(year=cursor.year - 1)

    return {
        "granularite": granularite,
        "points": list(reversed(buckets)),
    }


def _stats_charge(reclamations: list[models.Reclamation], now: datetime) -> dict:
    """Calcule les compteurs à_traiter / en_cours / traités + SLA + délai moyen."""
    a_traiter = en_cours = traites = en_alerte = echus = 0
    delais = []
    for r in reclamations:
        cat = wf.categorie_pilotage(r.statut)
        if cat == "a_traiter": a_traiter += 1
        elif cat == "en_cours": en_cours += 1
        else: traites += 1
        if r.statut not in wf.STATUTS_TRAITES:
            s = sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
            if s == "ALERTE": en_alerte += 1
            elif s == "ECHU": echus += 1
        if r.date_cloture:
            delais.append((r.date_cloture - r.date_reception).total_seconds() / 3600)
    actifs = a_traiter + en_cours
    return {
        "total": a_traiter + en_cours + traites,
        "a_traiter": a_traiter,
        "en_cours": en_cours,
        "traites": traites,
        "en_alerte_sla": en_alerte,
        "sla_echus": echus,
        "actifs": actifs,
        "taux_cloture_pct": round(traites / (a_traiter + en_cours + traites) * 100, 1)
            if (a_traiter + en_cours + traites) else 0.0,
        "delai_moyen_heures": round(sum(delais) / len(delais), 1) if delais else 0.0,
    }


@router.get("/par-agent")
def par_agent(
    periode: str = Query("annee"),
    date_ref: datetime | None = None,
    inclure_non_affectees: bool = Query(True),
    db: Session = Depends(get_db),
):
    """Stats par agent affecté : nombre à traiter / en cours / traités + SLA."""
    date_ref = date_ref or datetime.utcnow()
    debut, fin = _bornes_periode(periode, date_ref)
    now = datetime.utcnow()

    agents = list(db.scalars(select(models.Agent)))
    par_agent_map: dict[int | None, list[models.Reclamation]] = defaultdict(list)
    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    for r in toutes:
        par_agent_map[r.id_agent_affecte].append(r)

    items = []
    for a in agents:
        recs = par_agent_map.get(a.id, [])
        if not recs and a.role not in {"AGENT", "GESTIONNAIRE", "SUPERVISEUR"}:
            continue
        stats = _stats_charge(recs, now)
        items.append({
            "id_agent": a.id,
            "nom_complet": f"{a.prenom} {a.nom}",
            "role": a.role,
            "username": a.username,
            "actif": a.actif,
            "equipe": a.equipe.libelle if a.equipe else None,
            "id_equipe": a.id_equipe,
            **stats,
        })

    if inclure_non_affectees and par_agent_map.get(None):
        stats = _stats_charge(par_agent_map[None], now)
        items.append({
            "id_agent": None,
            "nom_complet": "Non assignées",
            "role": None, "username": None, "actif": True,
            "equipe": None, "id_equipe": None,
            **stats,
        })

    items.sort(key=lambda x: (x["a_traiter"] + x["en_cours"]), reverse=True)
    return {
        "periode": periode,
        "date_debut": debut.isoformat(),
        "date_fin": fin.isoformat(),
        "items": items,
    }


@router.get("/par-equipe")
def par_equipe(
    periode: str = Query("annee"),
    date_ref: datetime | None = None,
    db: Session = Depends(get_db),
):
    """Stats par équipe affectée : volumes + SLA + nb agents actifs de l'équipe."""
    date_ref = date_ref or datetime.utcnow()
    debut, fin = _bornes_periode(periode, date_ref)
    now = datetime.utcnow()

    equipes = list(db.scalars(select(models.Equipe).order_by(models.Equipe.libelle)))
    par_eq_map: dict[int | None, list[models.Reclamation]] = defaultdict(list)
    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    for r in toutes:
        par_eq_map[r.id_equipe_affectee].append(r)

    items = []
    for e in equipes:
        recs = par_eq_map.get(e.id, [])
        stats = _stats_charge(recs, now)
        nb_membres = sum(1 for m in e.membres if m.actif)
        items.append({
            "id_equipe": e.id,
            "code": e.code,
            "libelle": e.libelle,
            "nb_membres_actifs": nb_membres,
            **stats,
        })

    if par_eq_map.get(None):
        stats = _stats_charge(par_eq_map[None], now)
        items.append({
            "id_equipe": None, "code": None, "libelle": "Non affectées",
            "nb_membres_actifs": 0, **stats,
        })

    items.sort(key=lambda x: x["total"], reverse=True)
    return {
        "periode": periode,
        "date_debut": debut.isoformat(),
        "date_fin": fin.isoformat(),
        "items": items,
    }


@router.get("/causes-racines")
def causes_racines(
    mois: int = Query(6, ge=1, le=24),
    seuil_similarite: float = Query(0.35, ge=0.1, le=0.9),
    db: Session = Depends(get_db),
):
    """Détecte les clusters de réclamations récurrentes (BR010 + FR054)."""
    from ..services import cause_racine
    return cause_racine.analyser(db, mois=mois, seuil_similarite=seuil_similarite)


@router.get("/conformite-sla")
def conformite_sla(
    dim: str = Query("priorite", description="categorie, priorite, canal, equipe"),
    periode: str = Query("mois"),
    date_ref: datetime | None = None,
    db: Session = Depends(get_db),
):
    """Mesure de conformité SLA détaillée — utile pour les contrôles de conformité."""
    if dim not in {"categorie", "priorite", "canal", "equipe"}:
        raise HTTPException(422, "dim invalide pour conformité.")
    date_ref = date_ref or datetime.utcnow()
    debut, fin = _bornes_periode(periode, date_ref)

    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    now = datetime.utcnow()

    par_cle: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "ok": 0, "alerte": 0, "echu": 0, "termine": 0}
    )
    for r in toutes:
        cle = _cle_dimension(r, dim)
        d = par_cle[cle]
        d["total"] += 1
        s = sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        d[s.lower()] += 1

    items = []
    for cle, d in par_cle.items():
        actifs = d["ok"] + d["alerte"] + d["echu"]
        items.append({
            "modalite": cle,
            "total": d["total"],
            "ok": d["ok"], "alerte": d["alerte"], "echu": d["echu"], "termine": d["termine"],
            "conformite_pct": round(d["ok"] / actifs * 100, 1) if actifs else None,
        })
    items.sort(key=lambda x: (x["conformite_pct"] is None, x["conformite_pct"] or 0))
    return {
        "dimension": dim, "periode": periode,
        "date_debut": debut.isoformat(), "date_fin": fin.isoformat(),
        "items": items,
    }
