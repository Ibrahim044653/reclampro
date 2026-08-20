"""Service d'authentification : hash bcrypt + JWT HS256.

Volontairement minimaliste pour un MVP — pas de refresh token, pas de
rotation de clé. Pour la prod il faudra ajouter ces aspects.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt
from sqlalchemy.orm import Session
from sqlalchemy import select

from ..config import JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRATION_HEURES
from ..models import Agent


def hasher_mot_de_passe(mdp: str) -> str:
    return bcrypt.hashpw(mdp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verifier_mot_de_passe(mdp: str, hash_stocke: str) -> bool:
    try:
        return bcrypt.checkpw(mdp.encode("utf-8"), hash_stocke.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def creer_token(agent: Agent) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HEURES)
    payload = {
        "sub": str(agent.id),
        "username": agent.username,
        "role": agent.role,
        "exp": expire,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decoder_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def authentifier(db: Session, username: str, mdp: str) -> Optional[Agent]:
    agent = db.scalar(select(Agent).where(Agent.username == username))
    if not agent or not agent.actif or not agent.password_hash:
        return None
    if not verifier_mot_de_passe(mdp, agent.password_hash):
        return None
    return agent
