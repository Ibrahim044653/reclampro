"""Paramètres globaux de l'application.

Toutes les valeurs sensibles ou variables d'environnement
sont regroupées ici pour un débutant : un seul fichier à modifier.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def _build_db_url() -> str:
    from urllib.parse import urlparse, urlencode, urlunparse, parse_qs
    raw = os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'reclamations.db'}")
    # Normalise le schéma pour SQLAlchemy + psycopg2
    for old, new in [("postgresql://", "postgresql+psycopg2://"),
                     ("postgres://", "postgresql+psycopg2://")]:
        if raw.startswith(old):
            raw = new + raw[len(old):]
            break
    # Retire les paramètres non supportés par psycopg2
    parsed = urlparse(raw)
    params = parse_qs(parsed.query, keep_blank_values=True)
    for bad in ("channel_binding",):
        params.pop(bad, None)
    clean_query = urlencode({k: v[0] for k, v in params.items()})
    return urlunparse(parsed._replace(query=clean_query))

DATABASE_URL = _build_db_url()

ENTITE_CODE = "RECB"

SLA_HEURES = {
    "STANDARD": 5 * 24,
    "URGENT": 72,
    "CRITIQUE": 24,
}

SEUIL_ALERTE_SLA = 0.80

SEUIL_VALIDATION_FCFA = 500_000

CORS_ORIGINS = ["*"]

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret-change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HEURES = 8

EMAIL_DRIVER = os.getenv("EMAIL_DRIVER", "console")  # console | smtp
SMTP_HOST = os.getenv("SMTP_HOST", "localhost")
SMTP_PORT = int(os.getenv("SMTP_PORT", "1025"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_TLS = os.getenv("SMTP_TLS", "false").lower() == "true"
SMTP_FROM = os.getenv("SMTP_FROM", "no-reply@reclampro.local")

# IMAP entrant — boîte « reclamations@… » qui crée automatiquement les dossiers.
IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
IMAP_USER = os.getenv("IMAP_USER", "")
IMAP_PASSWORD = os.getenv("IMAP_PASSWORD", "")
IMAP_FOLDER = os.getenv("IMAP_FOLDER", "INBOX")

# Conservation BCEAO/CIMA (RG011) : archivage à J+5 ans, anonymisation à J+10 ans.
ARCHIVAGE_APRES_JOURS = int(os.getenv("ARCHIVAGE_APRES_JOURS", str(5 * 365)))
ANONYMISATION_APRES_JOURS = int(os.getenv("ANONYMISATION_APRES_JOURS", str(10 * 365)))

# WhatsApp Business Cloud API (Meta)
WHATSAPP_DRIVER = os.getenv("WHATSAPP_DRIVER", "console")  # console | cloud
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "dev-verify-token")
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "https://graph.facebook.com/v21.0")

# Sur Vercel le filesystem est en lecture seule — on utilise /tmp
_upload_env = os.getenv("UPLOAD_DIR", "")
UPLOAD_DIR = Path(_upload_env) if _upload_env else (Path("/tmp/uploads") if os.getenv("VERCEL") else BASE_DIR / "uploads")
UPLOAD_TAILLE_MAX = 10 * 1024 * 1024  # 10 MB
UPLOAD_MIME_AUTORISES = {
    "application/pdf",
    "image/jpeg", "image/png", "image/webp", "image/gif",
    "audio/mpeg", "audio/ogg", "audio/wav",
    "text/plain", "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
}
