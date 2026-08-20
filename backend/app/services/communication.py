"""Service d'envoi de communications client (email / SMS).

Driver « console » par défaut : log dans stdout + dans la table Interaction
(preuve d'envoi). Driver « smtp » : envoi réel via SMTP standard.

Pour activer SMTP en prod :
    set EMAIL_DRIVER=smtp
    set SMTP_HOST=smtp.exemple.ci
    set SMTP_PORT=587
    set SMTP_USER=...
    set SMTP_PASSWORD=...
    set SMTP_TLS=true
    set SMTP_FROM=reclamations@banque.ci
"""
from __future__ import annotations
import logging
import smtplib
from email.message import EmailMessage

from .. import config

logger = logging.getLogger("communication")


def _envoyer_smtp(destinataire: str, sujet: str, corps: str) -> bool:
    """Envoi SMTP réel. Retourne True/False."""
    msg = EmailMessage()
    msg["Subject"] = sujet
    msg["From"] = config.SMTP_FROM
    msg["To"] = destinataire
    msg.set_content(corps)
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as s:
            if config.SMTP_TLS:
                s.starttls()
            if config.SMTP_USER:
                s.login(config.SMTP_USER, config.SMTP_PASSWORD)
            s.send_message(msg)
        return True
    except Exception as exc:
        logger.warning("Echec envoi SMTP vers %s : %s", destinataire, exc)
        return False


def envoyer_email(destinataire: str | None, sujet: str, corps: str) -> dict:
    """Envoie un email. Retourne un dict de preuve d'envoi."""
    if not destinataire:
        return {"statut": "IGNORE", "raison": "Pas d'adresse email"}

    if config.EMAIL_DRIVER == "smtp":
        ok = _envoyer_smtp(destinataire, sujet, corps)
        return {
            "statut": "ENVOYE" if ok else "ECHEC",
            "driver": "smtp",
            "destinataire": destinataire,
            "host": f"{config.SMTP_HOST}:{config.SMTP_PORT}",
        }

    # Driver console (mode dev / démo)
    logger.info("[EMAIL → %s] %s\n%s", destinataire, sujet, corps)
    return {
        "statut": "SIMULE",
        "driver": "console",
        "destinataire": destinataire,
        "sujet": sujet,
    }


# ===== Templates =====

def template_acr(reclamation, client) -> tuple[str, str]:
    """Template d'accusé de réception (BR008 / RG006)."""
    sujet = f"Accusé de réception de votre réclamation {reclamation.code}"
    corps = f"""Bonjour {client.prenom} {client.nom},

Nous accusons bonne réception de votre réclamation enregistrée sous la référence :

    {reclamation.code}

Elle sera traitée dans les délais réglementaires applicables.
Vous pouvez suivre l'avancement via le lien qui vous sera communiqué.

Pour toute question, contactez notre service réclamations.

Cordialement,
Le service réclamations
"""
    return sujet, corps


def template_cloture(reclamation, client) -> tuple[str, str]:
    motifs_lib = {
        "FAVORABLE": "Favorable", "PARTIEL": "Partiellement favorable",
        "DEFAVORABLE": "Défavorable", "SANS_SUITE": "Classé sans suite",
        "MEDIATION": "Redirection vers médiation",
    }
    motif = motifs_lib.get(reclamation.motif_cloture, reclamation.motif_cloture)
    sujet = f"Décision concernant votre réclamation {reclamation.code}"
    corps = f"""Bonjour {client.prenom} {client.nom},

Votre réclamation {reclamation.code} a fait l'objet de la décision suivante :

    {motif}

Si vous contestez cette décision, vous avez la possibilité de saisir le médiateur
ou les autorités de régulation compétentes (BCEAO / CIMA).

Cordialement,
Le service réclamations
"""
    return sujet, corps
