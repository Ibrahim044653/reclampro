"""KPIs et données du dashboard de supervision."""
from datetime import datetime, timedelta
from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from .. import models, schemas, crud
from ..database import get_db
from ..services import sla as sla_service
from .auth import utilisateur_courant

router = APIRouter(
    prefix="/api/dashboard",
    tags=["dashboard"],
    dependencies=[Depends(utilisateur_courant)],
)


def _repartition(items: list[str], libelles: dict[str, str] | None = None) -> list[schemas.RepartitionItem]:
    total = len(items) or 1
    compteur = Counter(items)
    libelles = libelles or {}
    return [
        schemas.RepartitionItem(
            label=libelles.get(k, k),
            valeur=v,
            pourcentage=round(v / total * 100, 1),
        )
        for k, v in compteur.most_common()
    ]


@router.get("", response_model=schemas.DashboardData)
def donnees(db: Session = Depends(get_db)):
    now = datetime.utcnow()
    debut_mois = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    toutes = list(db.scalars(select(models.Reclamation)))
    ce_mois = [r for r in toutes if r.date_reception >= debut_mois]
    en_cours = [r for r in toutes if r.statut not in {"CLOTURE", "REJETE"}]
    cloturees_mois = [r for r in ce_mois if r.statut == "CLOTURE"]

    sla_par_dossier = {
        r.id: sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        for r in toutes
    }
    en_alerte = [r for r in en_cours if sla_par_dossier[r.id] == "ALERTE"]
    echus = [r for r in en_cours if sla_par_dossier[r.id] == "ECHU"]

    resolues_dans_5j = sum(
        1 for r in cloturees_mois
        if r.date_cloture and (r.date_cloture - r.date_reception) <= timedelta(days=5)
    )
    taux = round(resolues_dans_5j / len(cloturees_mois) * 100, 1) if cloturees_mois else 0.0

    kpi = schemas.DashboardKPI(
        recues_mois=len(ce_mois),
        en_cours=len(en_cours),
        en_alerte_sla=len(en_alerte),
        cloturees=len(cloturees_mois),
        sla_depasses=len(echus),
        taux_resolution_5j=taux,
    )

    libelles_canal = {
        "EMAIL": "Email", "AGENCE": "Agence", "WHATSAPP": "WhatsApp",
        "TELEPHONE": "Téléphone", "WEB": "Web", "COURRIER": "Courrier",
    }
    repartition_canal = _repartition([r.canal for r in ce_mois], libelles_canal)
    repartition_categorie = _repartition([r.categorie for r in ce_mois])
    repartition_priorite = _repartition([r.priorite for r in ce_mois])

    libelles_sla = {"OK": "Conforme", "ALERTE": "En alerte", "ECHU": "Échu", "TERMINE": "Terminé"}
    repartition_sla = _repartition(list(sla_par_dossier.values()), libelles_sla)

    volume_hebdo = []
    for i in range(5, -1, -1):
        debut = now - timedelta(weeks=i + 1)
        fin = now - timedelta(weeks=i)
        semaine = [r for r in toutes if debut <= r.date_reception < fin]
        volume_hebdo.append({
            "semaine": f"S{(now - timedelta(weeks=i)).isocalendar().week}",
            "recues": len(semaine),
            "cloturees": sum(1 for r in semaine if r.statut == "CLOTURE"),
        })

    mois_labels = ["Jan", "Fév", "Mar", "Avr", "Mai", "Jun", "Jui", "Aoû", "Sep", "Oct", "Nov", "Déc"]
    volume_mensuel = []
    for i in range(5, -1, -1):
        date_ref = (now.replace(day=1) - timedelta(days=1) * (i * 30)).replace(day=1)
        month_start = (now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))
        for _ in range(i):
            month_start = (month_start - timedelta(days=1)).replace(day=1)
        next_month = (month_start + timedelta(days=32)).replace(day=1)
        m = [r for r in toutes if month_start <= r.date_reception < next_month]
        volume_mensuel.append({
            "mois": mois_labels[month_start.month - 1],
            "annee": month_start.year,
            "recues": len(m),
            "cloturees": sum(1 for r in m if r.statut == "CLOTURE"),
        })

    fin_journee = now.replace(hour=23, minute=59, second=59)
    echeances_jour = sum(
        1 for r in en_cours
        if r.date_echeance_sla <= fin_journee
        and r.date_echeance_sla >= now.replace(hour=0, minute=0, second=0)
    )

    alertes = sorted(en_alerte + echus, key=lambda r: r.date_echeance_sla)[:10]
    alertes_out = [
        schemas.ReclamationOut.model_validate(r).model_copy(update=crud.annoter_sla(r, now))
        for r in alertes
    ]

    return schemas.DashboardData(
        kpi=kpi,
        repartition_canal=repartition_canal,
        repartition_categorie=repartition_categorie,
        repartition_priorite=repartition_priorite,
        repartition_sla=repartition_sla,
        volume_hebdo=volume_hebdo,
        volume_mensuel=volume_mensuel,
        alertes_sla=alertes_out,
        echeances_jour=echeances_jour,
        aujourd_hui=now.strftime("%Y-%m-%d"),
    )
