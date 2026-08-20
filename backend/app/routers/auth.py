"""Endpoints d'authentification + dependencies pour protéger les routes."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..services import auth as auth_service, mfa as mfa_service

router = APIRouter(prefix="/api/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    username: str
    password: str
    code_mfa: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    utilisateur: schemas.AgentOut


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    agent = auth_service.authentifier(db, payload.username, payload.password)
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiants invalides.",
        )
    if agent.mfa_active:
        if not payload.code_mfa:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="MFA_REQUIRED",
            )
        if not mfa_service.verifier_code(agent.totp_secret, payload.code_mfa):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Code MFA invalide.",
            )
    token = auth_service.creer_token(agent)
    return LoginResponse(access_token=token, utilisateur=agent)


def utilisateur_courant(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> models.Agent:
    """Décode le JWT et retourne l'agent. Lève 401 si invalide/expiré."""
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentification requise.")
    payload = auth_service.decoder_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token invalide ou expiré.")
    agent = db.get(models.Agent, int(payload["sub"]))
    if agent is None or not agent.actif:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Compte inconnu ou désactivé.")
    return agent


def utilisateur_admin(agent: models.Agent = Depends(utilisateur_courant)) -> models.Agent:
    if agent.role != "ADMIN":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Droits administrateur requis.")
    return agent


@router.get("/me", response_model=schemas.AgentOut)
def me(agent: models.Agent = Depends(utilisateur_courant)):
    return agent


class MfaSetupResponse(BaseModel):
    secret: str
    uri: str
    qr_code_png_base64: str


class MfaActivateRequest(BaseModel):
    code: str


class MfaDisableRequest(BaseModel):
    password: str


@router.post("/mfa/setup", response_model=MfaSetupResponse)
def mfa_setup(
    db: Session = Depends(get_db),
    agent: models.Agent = Depends(utilisateur_courant),
):
    """Génère un nouveau secret TOTP. Ne l'active pas — il faut /mfa/activate."""
    if agent.mfa_active:
        raise HTTPException(409, "MFA déjà activée. La désactiver d'abord.")
    secret = mfa_service.generer_secret()
    agent.totp_secret = secret
    db.commit()
    uri = mfa_service.provisioning_uri(agent.username or agent.email_pro, secret)
    return MfaSetupResponse(
        secret=secret,
        uri=uri,
        qr_code_png_base64=mfa_service.qr_code_base64(uri),
    )


@router.post("/mfa/activate", status_code=204)
def mfa_activate(
    payload: MfaActivateRequest,
    db: Session = Depends(get_db),
    agent: models.Agent = Depends(utilisateur_courant),
):
    if not agent.totp_secret:
        raise HTTPException(409, "Aucun secret TOTP généré. Lancer /mfa/setup d'abord.")
    if not mfa_service.verifier_code(agent.totp_secret, payload.code):
        raise HTTPException(401, "Code MFA invalide.")
    agent.mfa_active = True
    db.commit()


@router.post("/mfa/desactiver", status_code=204)
def mfa_desactiver(
    payload: MfaDisableRequest,
    db: Session = Depends(get_db),
    agent: models.Agent = Depends(utilisateur_courant),
):
    """Désactivation : on re-vérifie le mot de passe pour éviter la prise de contrôle."""
    if not auth_service.verifier_mot_de_passe(payload.password, agent.password_hash or ""):
        raise HTTPException(401, "Mot de passe incorrect.")
    agent.mfa_active = False
    agent.totp_secret = None
    db.commit()
