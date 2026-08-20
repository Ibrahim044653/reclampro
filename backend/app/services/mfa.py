"""Service MFA TOTP (RFC 6238) — compatible Google Authenticator / Authy."""
import io
import base64
import pyotp
import qrcode


def generer_secret() -> str:
    return pyotp.random_base32()


def verifier_code(secret: str, code: str) -> bool:
    if not secret or not code:
        return False
    code = code.replace(" ", "").strip()
    return pyotp.TOTP(secret).verify(code, valid_window=1)


def provisioning_uri(username: str, secret: str, issuer: str = "RéclamPro") -> str:
    """URI standard otpauth:// utilisée par les apps d'authentification."""
    return pyotp.TOTP(secret).provisioning_uri(name=username, issuer_name=issuer)


def qr_code_base64(uri: str) -> str:
    """Génère un PNG en base64 du QR code (pour affichage <img src='data:image/png;base64,...'>)."""
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")
