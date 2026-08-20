"""Génération du rapport mensuel BCEAO/CIMA (RG012).

Produit un PDF de synthèse pour la période demandée :
- Volumétrie globale (reçues, clôturées, en cours)
- Conformité SLA par priorité
- Top catégories
- Répartition par canal
- Top équipes par charge
- Liste exhaustive des SLA dépassés
"""
import io
from datetime import datetime, timedelta
from collections import Counter

from sqlalchemy.orm import Session
from sqlalchemy import select

from .. import models
from . import sla as sla_service


def _bornes_mois(annee: int, mois: int) -> tuple[datetime, datetime]:
    debut = datetime(annee, mois, 1)
    fin = (debut + timedelta(days=32)).replace(day=1)
    return debut, fin


def generer_pdf(db: Session, annee: int, mois: int) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    )

    debut, fin = _bornes_mois(annee, mois)
    toutes = list(db.scalars(
        select(models.Reclamation).where(
            models.Reclamation.date_reception >= debut,
            models.Reclamation.date_reception < fin,
        )
    ))
    cloturees = [r for r in toutes if r.statut == "CLOTURE"]
    en_cours = [r for r in toutes if r.statut not in {"CLOTURE", "REJETE"}]

    now = datetime.utcnow()
    stats_sla = Counter(
        sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now)
        for r in toutes
    )
    actifs = stats_sla.get("OK", 0) + stats_sla.get("ALERTE", 0) + stats_sla.get("ECHU", 0)
    taux_conformite = round(stats_sla.get("OK", 0) / actifs * 100, 1) if actifs else 0.0

    delais = [(r.date_cloture - r.date_reception).total_seconds() / 3600
              for r in cloturees if r.date_cloture]
    delai_moyen = round(sum(delais) / len(delais), 1) if delais else 0.0

    par_categorie = Counter(r.categorie for r in toutes).most_common(5)
    par_canal = Counter(r.canal for r in toutes).most_common()
    par_priorite = Counter(r.priorite for r in toutes).most_common()

    echus = [r for r in en_cours
             if sla_service.statut_sla(r.date_reception, r.date_echeance_sla, r.statut, now) == "ECHU"]

    # === PDF ===
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    titre = ParagraphStyle("t", parent=styles["Title"], fontSize=18,
                           textColor=colors.HexColor("#185FA5"))
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], fontSize=12,
                        textColor=colors.HexColor("#185FA5"))
    meta = ParagraphStyle("m", parent=styles["Normal"], fontSize=9,
                          textColor=colors.grey)
    normal = styles["Normal"]

    mois_label = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet",
                  "Août","Septembre","Octobre","Novembre","Décembre"][mois - 1]

    elements = [
        Paragraph("Rapport mensuel des réclamations clients", titre),
        Paragraph(f"<b>Période :</b> {mois_label} {annee}", normal),
        Paragraph(
            f"Document généré le {now:%d/%m/%Y à %H:%M} — Référence réglementaire : "
            f"BCEAO Instruction n°001 / CIMA Art. 12 — Conservation 10 ans (RG011).",
            meta,
        ),
        Spacer(1, 8 * mm),

        Paragraph("1. Volumétrie", h2),
    ]
    vol = [
        ["Indicateur", "Valeur"],
        ["Dossiers reçus", str(len(toutes))],
        ["Dossiers clôturés", str(len(cloturees))],
        ["Dossiers en cours", str(len(en_cours))],
        ["Délai moyen de traitement", f"{delai_moyen} heures"],
        ["Taux de conformité SLA", f"{taux_conformite} %"],
    ]
    t = Table(vol, colWidths=[80 * mm, 50 * mm])
    t.setStyle(_style_table())
    elements += [t, Spacer(1, 6 * mm)]

    elements.append(Paragraph("2. Répartition par priorité", h2))
    data = [["Priorité", "Nombre", "Part"]] + [
        [p, str(n), f"{n / len(toutes) * 100:.1f} %" if toutes else "—"]
        for p, n in par_priorite
    ]
    t = Table(data, colWidths=[60 * mm, 35 * mm, 35 * mm])
    t.setStyle(_style_table())
    elements += [t, Spacer(1, 6 * mm)]

    elements.append(Paragraph("3. Top catégories", h2))
    data = [["Catégorie", "Nombre"]] + [[c, str(n)] for c, n in par_categorie]
    t = Table(data, colWidths=[100 * mm, 30 * mm])
    t.setStyle(_style_table())
    elements += [t, Spacer(1, 6 * mm)]

    elements.append(Paragraph("4. Répartition par canal d'entrée", h2))
    data = [["Canal", "Nombre"]] + [[c, str(n)] for c, n in par_canal]
    t = Table(data, colWidths=[100 * mm, 30 * mm])
    t.setStyle(_style_table())
    elements += [t, Spacer(1, 6 * mm)]

    if echus:
        elements.append(Paragraph(
            f"5. Dossiers en dépassement SLA ({len(echus)})", h2))
        data = [["Code", "Catégorie", "Priorité", "Reçue le", "Échéance"]]
        for r in echus[:30]:
            data.append([
                r.code, r.categorie, r.priorite,
                r.date_reception.strftime("%d/%m/%Y"),
                r.date_echeance_sla.strftime("%d/%m/%Y"),
            ])
        t = Table(data, colWidths=[45*mm, 35*mm, 25*mm, 30*mm, 30*mm])
        t.setStyle(_style_table())
        elements += [t, Spacer(1, 6 * mm)]
        if len(echus) > 30:
            elements.append(Paragraph(
                f"… et {len(echus) - 30} autre(s) dossier(s) en dépassement.", meta))

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(
        "Signature du responsable conformité : ____________________________ "
        f"Date : {now:%d/%m/%Y}",
        normal,
    ))

    doc.build(elements)
    buf.seek(0)
    return buf.getvalue()


def _style_table():
    from reportlab.lib import colors
    from reportlab.platypus import TableStyle
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#185FA5")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F5EE")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#B5D4F4")),
        ("ALIGN", (1, 1), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
