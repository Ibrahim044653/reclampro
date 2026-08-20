"""Calcul SLA (RG001-RG004).

- Date d'échéance = date_reception + délai_priorité
- Alerte à 80% du SLA écoulé
- "Échu" si on a dépassé 100%
"""
from datetime import datetime, timedelta

from ..config import SLA_HEURES, SEUIL_ALERTE_SLA


def calculer_echeance(date_reception: datetime, priorite: str) -> datetime:
    heures = SLA_HEURES.get(priorite, SLA_HEURES["STANDARD"])
    return date_reception + timedelta(hours=heures)


def pourcentage_consomme(
    date_reception: datetime, date_echeance: datetime, now: datetime | None = None
) -> float:
    now = now or datetime.utcnow()
    total = (date_echeance - date_reception).total_seconds()
    if total <= 0:
        return 1.0
    ecoule = (now - date_reception).total_seconds()
    return max(0.0, min(ecoule / total, 1.5))


def statut_sla(
    date_reception: datetime,
    date_echeance: datetime,
    statut_dossier: str,
    now: datetime | None = None,
) -> str:
    """Retourne OK / ALERTE / ECHU / TERMINE selon l'avancement."""
    if statut_dossier in {"CLOTURE", "REJETE"}:
        return "TERMINE"
    pct = pourcentage_consomme(date_reception, date_echeance, now)
    if pct >= 1.0:
        return "ECHU"
    if pct >= SEUIL_ALERTE_SLA:
        return "ALERTE"
    return "OK"
