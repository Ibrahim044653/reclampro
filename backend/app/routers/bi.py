"""Endpoints JSON pour connecteurs BI externes (Power BI, Tableau, Metabase…).

Authentification : Bearer JWT classique. Dans Power BI :
    Source > Web > URL avancée
    URL : http://api.reclampro.local/api/bi/reclamations
    En-tête HTTP : Authorization = Bearer <jeton>
"""
from datetime import datetime
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models
from ..database import get_db
from ..services import sla as sla_service
from .auth import utilisateur_admin

router = APIRouter(prefix="/api/bi", tags=["bi"],
                   dependencies=[Depends(utilisateur_admin)])


@router.get("/reclamations")
def export_reclamations_flat(db: Session = Depends(get_db)):
    """Table plate prête pour ingestion BI : 1 ligne = 1 dossier, joints aplatis."""
    now = datetime.utcnow()
    items = list(db.scalars(select(models.Reclamation)))
    sortie = []
    for r in items:
        delai_traitement_h = None
        if r.date_cloture:
            delai_traitement_h = round(
                (r.date_cloture - r.date_reception).total_seconds() / 3600, 1
            )
        sortie.append({
            "code": r.code,
            "canal": r.canal,
            "statut": r.statut,
            "categorie": r.categorie,
            "sous_categorie": r.sous_categorie,
            "priorite": r.priorite,
            "montant_enjeu_fcfa": r.montant_enjeu,
            "date_reception": r.date_reception.isoformat(),
            "date_echeance_sla": r.date_echeance_sla.isoformat(),
            "date_cloture": r.date_cloture.isoformat() if r.date_cloture else None,
            "motif_cloture": r.motif_cloture,
            "delai_traitement_heures": delai_traitement_h,
            "sla_statut": sla_service.statut_sla(
                r.date_reception, r.date_echeance_sla, r.statut, now,
            ),
            "sla_pourcentage_consomme": round(sla_service.pourcentage_consomme(
                r.date_reception, r.date_echeance_sla, now,
            ) * 100, 1),
            "id_entite": r.id_entite,
            "entite_libelle": r.entite_affectee_libelle(),
            "equipe_libelle": r.equipe_affectee.libelle if r.equipe_affectee else None,
            "agent_affecte": (
                f"{r.agent_affecte.prenom} {r.agent_affecte.nom}"
                if r.agent_affecte else None
            ),
            "client_segment": r.client.type if r.client else None,
            "annee": r.date_reception.year,
            "mois": r.date_reception.month,
            "trimestre": (r.date_reception.month - 1) // 3 + 1,
            "semaine_iso": r.date_reception.isocalendar().week,
            "jour_semaine": r.date_reception.strftime("%A"),
            "archivee": r.archivee,
            "anonymisee": r.anonymisee,
        })
    return {"items": sortie, "total": len(sortie), "generated_at": now.isoformat()}


@router.get("/agregats-quotidiens")
def agregats_quotidiens(db: Session = Depends(get_db)):
    """Série temporelle quotidienne agrégée — idéale pour dashboards BI."""
    items = list(db.scalars(select(models.Reclamation)))
    par_jour: dict[str, dict] = {}
    for r in items:
        cle = r.date_reception.strftime("%Y-%m-%d")
        if cle not in par_jour:
            par_jour[cle] = {
                "date": cle, "recues": 0, "cloturees": 0,
                "critique": 0, "urgent": 0, "standard": 0,
                "par_canal": Counter(), "par_categorie": Counter(),
            }
        d = par_jour[cle]
        d["recues"] += 1
        if r.statut == "CLOTURE":
            d["cloturees"] += 1
        d[r.priorite.lower()] = d.get(r.priorite.lower(), 0) + 1
        d["par_canal"][r.canal] += 1
        d["par_categorie"][r.categorie] += 1

    sortie = []
    for cle, d in sorted(par_jour.items()):
        d["par_canal"] = dict(d["par_canal"])
        d["par_categorie"] = dict(d["par_categorie"])
        sortie.append(d)
    return {"series": sortie, "total_jours": len(sortie)}


@router.get("/kpi-temps-reel")
def kpi_temps_reel(db: Session = Depends(get_db)):
    """KPI live pour dashboard auto-refresh BI."""
    now = datetime.utcnow()
    items = list(db.scalars(select(models.Reclamation)))
    en_cours = [r for r in items if r.statut not in {"CLOTURE", "REJETE"}]
    stats_sla = Counter(
        sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        for r in en_cours
    )
    return {
        "timestamp": now.isoformat(),
        "total": len(items),
        "en_cours": len(en_cours),
        "cloturees": sum(1 for r in items if r.statut == "CLOTURE"),
        "sla_ok": stats_sla.get("OK", 0),
        "sla_alerte": stats_sla.get("ALERTE", 0),
        "sla_echu": stats_sla.get("ECHU", 0),
    }


# Petit patch sur le modèle Reclamation pour exposer le libellé entité
def _entite_libelle(self):
    if self.id_entite is None:
        return None
    # On évite un lookup si pas chargé (lazy ok ici)
    if self.equipe_affectee and self.equipe_affectee.entite:
        return self.equipe_affectee.entite.libelle
    return None


models.Reclamation.entite_affectee_libelle = _entite_libelle
