"""Chiffrement applicatif des champs personnels (NFR005 du CDC).

Approche : type SQLAlchemy custom `EncryptedString` qui chiffre à l'écriture
et déchiffre à la lecture. La clé maître est dans la config — en prod il faut
la stocker dans un KMS / vault, pas dans le code.

L'algorithme retenu est Fernet (AES-128-CBC + HMAC-SHA256), de la lib
`cryptography`. Il garantit confidentialité + authenticité.
"""
import base64
import os
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy.types import TypeDecorator, String


def _normaliser_cle(cle_brute: str) -> bytes:
    """Convertit la clé config en clé Fernet (32 octets URL-safe base64)."""
    bytes_brute = cle_brute.encode("utf-8")
    # On dérive 32 octets en hashant si la clé est trop courte/longue.
    import hashlib
    digest = hashlib.sha256(bytes_brute).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET: Fernet | None = None


def fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        cle = os.getenv("APP_CRYPTO_KEY", "dev-key-change-me-in-production-please-32+chars")
        _FERNET = Fernet(_normaliser_cle(cle))
    return _FERNET


def chiffrer(valeur: str | None) -> str | None:
    if valeur is None or valeur == "":
        return valeur
    return fernet().encrypt(valeur.encode("utf-8")).decode("ascii")


def dechiffrer(token: str | None) -> str | None:
    if token is None or token == "":
        return token
    try:
        return fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        # Donnée non chiffrée (héritée d'une ancienne base) — on la rend telle quelle.
        return token


class EncryptedString(TypeDecorator):
    """Colonne chiffrée transparente.

    Usage : `email = Column(EncryptedString(500))`. La longueur doit prévoir
    l'expansion du chiffrement (~ 100 octets de base + 4/3 ratio).
    """
    impl = String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return chiffrer(value)

    def process_result_value(self, value, dialect):
        return dechiffrer(value)
