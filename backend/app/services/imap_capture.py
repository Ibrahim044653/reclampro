"""Capture des emails entrants (FR002).

Approche : un endpoint admin déclenche le traitement (polling manuel ou
cron externe). Pas de daemon long-lived.

Chaque email :
- Sujet → sous_categorie + description (corps texte)
- From → client (création si nouveau, déduplication via email_hash)
- Catégorie : "SERVICE" par défaut (l'admin peut requalifier)
- Canal : EMAIL
"""
from __future__ import annotations
import email
import imaplib
import logging
from email.header import decode_header
from email.utils import parseaddr

from sqlalchemy.orm import Session

from .. import config, schemas, crud

logger = logging.getLogger("imap_capture")


def _decode(val) -> str:
    if val is None:
        return ""
    parts = decode_header(val)
    res = []
    for txt, enc in parts:
        if isinstance(txt, bytes):
            try:
                res.append(txt.decode(enc or "utf-8", errors="replace"))
            except (LookupError, TypeError):
                res.append(txt.decode("utf-8", errors="replace"))
        else:
            res.append(txt)
    return "".join(res)


def _extraire_corps(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            disp = str(part.get("Content-Disposition") or "")
            if ctype == "text/plain" and "attachment" not in disp:
                try:
                    payload = part.get_payload(decode=True) or b""
                    return payload.decode(part.get_content_charset() or "utf-8",
                                          errors="replace").strip()
                except Exception:
                    continue
        return "(email multipart sans partie texte)"
    payload = msg.get_payload(decode=True) or b""
    return payload.decode(msg.get_content_charset() or "utf-8", errors="replace").strip()


def traiter_boite(db: Session, marquer_lus: bool = True) -> dict:
    """Connecte à l'IMAP, traite les messages non lus, crée les réclamations.

    Retourne un dict {nombre_traites, codes_crees, erreurs}.
    """
    if not config.IMAP_HOST or not config.IMAP_USER:
        return {"nombre_traites": 0, "codes_crees": [], "erreurs": ["IMAP non configuré (IMAP_HOST/USER vides)"]}

    codes = []
    erreurs = []
    try:
        client = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        client.login(config.IMAP_USER, config.IMAP_PASSWORD)
        client.select(config.IMAP_FOLDER)
        typ, data = client.search(None, "UNSEEN")
        if typ != "OK":
            return {"nombre_traites": 0, "codes_crees": [], "erreurs": ["Recherche IMAP échouée"]}

        ids = data[0].split()
        for msg_id in ids:
            try:
                typ, msg_data = client.fetch(msg_id, "(RFC822)")
                if typ != "OK":
                    continue
                msg = email.message_from_bytes(msg_data[0][1])
                expediteur_brut = _decode(msg.get("From"))
                nom, email_addr = parseaddr(expediteur_brut)
                sujet = _decode(msg.get("Subject")) or "(sans sujet)"
                corps = _extraire_corps(msg)
                if not email_addr:
                    erreurs.append(f"Email #{msg_id.decode()} sans expéditeur valide")
                    continue
                # Découpe nom complet en prénom/nom (best-effort)
                parties = (nom or email_addr.split("@")[0]).split()
                prenom = parties[0] if parties else "Client"
                nomfam = " ".join(parties[1:]) if len(parties) > 1 else "(inconnu)"

                description = (corps or sujet)[:5000]
                if len(description) < 10:
                    description = description + " — (email court)"

                payload = schemas.ReclamationCreate(
                    canal="EMAIL",
                    categorie="SERVICE",
                    sous_categorie=sujet[:80] or None,
                    priorite="STANDARD",
                    description=description,
                    montant_enjeu=0,
                    client=schemas.ClientCreate(
                        nom=nomfam, prenom=prenom, email=email_addr,
                    ),
                )
                r = crud.creer_reclamation(db, payload)
                codes.append(r.code)
                if marquer_lus:
                    client.store(msg_id, "+FLAGS", "\\Seen")
            except Exception as exc:
                logger.exception("Erreur traitement email")
                erreurs.append(f"Email #{msg_id}: {exc}")

        client.logout()
    except Exception as exc:
        return {"nombre_traites": 0, "codes_crees": codes, "erreurs": [str(exc)]}

    return {"nombre_traites": len(codes), "codes_crees": codes, "erreurs": erreurs}
