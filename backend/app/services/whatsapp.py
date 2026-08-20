"""Intégration WhatsApp Business Cloud API (FR003).

Deux drivers :
- `console` (par défaut, dev) : log dans stdout
- `cloud` (prod) : appel HTTP réel à l'API Meta Cloud

Configuration prod :
    WHATSAPP_DRIVER=cloud
    WHATSAPP_TOKEN=<bearer permanent ou system user>
    WHATSAPP_PHONE_NUMBER_ID=<id depuis le dashboard Meta>
    WHATSAPP_VERIFY_TOKEN=<token de webhook>
"""
import logging
import httpx

from .. import config

logger = logging.getLogger("whatsapp")


def envoyer_message(numero: str | None, message: str) -> dict:
    """Envoie un message texte WhatsApp. Retourne preuve d'envoi."""
    if not numero:
        return {"statut": "IGNORE", "raison": "Pas de numéro WhatsApp"}

    if config.WHATSAPP_DRIVER == "cloud":
        if not config.WHATSAPP_TOKEN or not config.WHATSAPP_PHONE_NUMBER_ID:
            return {"statut": "ECHEC", "raison": "WhatsApp Cloud non configuré"}

        url = f"{config.WHATSAPP_API_URL}/{config.WHATSAPP_PHONE_NUMBER_ID}/messages"
        try:
            r = httpx.post(
                url,
                headers={
                    "Authorization": f"Bearer {config.WHATSAPP_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "messaging_product": "whatsapp",
                    "to": numero,
                    "type": "text",
                    "text": {"body": message},
                },
                timeout=15.0,
            )
            r.raise_for_status()
            return {"statut": "ENVOYE", "driver": "cloud", "destinataire": numero,
                    "message_id": r.json().get("messages", [{}])[0].get("id")}
        except Exception as exc:
            logger.warning("Echec WhatsApp Cloud %s : %s", numero, exc)
            return {"statut": "ECHEC", "driver": "cloud", "raison": str(exc)}

    # Driver console
    logger.info("[WHATSAPP → %s] %s", numero, message)
    return {"statut": "SIMULE", "driver": "console", "destinataire": numero}


def parser_message_entrant(payload: dict) -> dict | None:
    """Extrait le numéro de l'expéditeur + texte d'un payload webhook Meta.

    Format Meta : {entry: [{changes: [{value: {messages: [...]}}]}]}
    """
    try:
        entries = payload.get("entry", [])
        for entry in entries:
            for change in entry.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])
                contacts = value.get("contacts", [])
                for msg in messages:
                    if msg.get("type") == "text":
                        return {
                            "from": msg.get("from"),
                            "nom_profil": contacts[0].get("profile", {}).get("name") if contacts else None,
                            "texte": msg.get("text", {}).get("body", ""),
                            "message_id": msg.get("id"),
                            "timestamp": msg.get("timestamp"),
                        }
    except (KeyError, AttributeError, TypeError):
        return None
    return None
