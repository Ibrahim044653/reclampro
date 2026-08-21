"""Point d'entrée FastAPI — lance avec : uvicorn app.main:app --reload"""
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import os
from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import (
    reclamations, dashboard, exports, agents, auth, users,
    equipes, notifications, reports, pieces_jointes, public,
    templates, approbations, imap, retention, whatsapp, bi, cron,
)

def _init_db():
    import logging
    _log = logging.getLogger(__name__)
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        _log.error("create_all error: %s", e)
        return
    # Migration incrémentale : ajoute les colonnes manquantes sans toucher aux données.
    try:
        from sqlalchemy import text, inspect as sa_inspect
        with engine.connect() as conn:
            col_names = [c["name"] for c in sa_inspect(engine).get_columns("reclamations")]
            if "tags" not in col_names:
                conn.execute(text("ALTER TABLE reclamations ADD COLUMN tags TEXT"))
                conn.commit()
                print("[INIT] Migration : colonne 'tags' ajoutée.", flush=True)
    except Exception as e:
        print(f"[INIT] Migration ignorée : {e}", flush=True)
    _seed_flag = os.getenv("SEED_AT_STARTUP", "").strip().lstrip('﻿').lower()
    print(f"[INIT] SEED_AT_STARTUP={repr(_seed_flag)}", flush=True)
    if _seed_flag != "true":
        return
    # Seed minimal et idempotent : crée admin + agent si absents
    try:
        from .database import SessionLocal
        from . import models
        from .services import auth as auth_svc
        db = SessionLocal()
        try:
            if db.query(models.Agent).filter_by(username="admin").first():
                return  # déjà seedé
            entite = models.Entite(code="RECB", libelle="Banque RéclamPro", type="BANQUE")
            db.add(entite); db.flush()
            equipe = models.Equipe(code="ADMIN", libelle="Administration",
                                   description="Équipe admin", id_entite=entite.id)
            db.add(equipe); db.flush()
            for username, mdp, role in [("admin", "admin123", "ADMIN"), ("agent", "agent123", "AGENT")]:
                db.add(models.Agent(
                    nom=username.capitalize(), prenom="Demo", email_pro=f"{username}@reclampro.ci",
                    role=role, service=equipe.libelle, username=username,
                    password_hash=auth_svc.hasher_mot_de_passe(mdp),
                    id_equipe=equipe.id, id_entite=entite.id,
                ))
            db.commit()
            print("[INIT] Seed minimal OK : admin + agent créés.", flush=True)
        finally:
            db.close()
    except Exception as e:
        print(f"[INIT] Seed error: {e}", flush=True)

_init_db()

app = FastAPI(
    title="RéclamPro — API gestion des réclamations",
    description="MVP conforme BCEAO/CIMA — capture, workflow, SLA, dashboard, registre.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting — protège les endpoints publics contre les abus.
# Sur Vercel serverless, le compteur est par instance (pas global).
# Pour un rate limiting global en prod, configurer REDIS_URL + slowapi avec Redis.
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_remote_address, default_limits=["300/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass  # slowapi optionnel — l'app démarre sans

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(users.router)
app.include_router(equipes.router)
app.include_router(notifications.router)
app.include_router(reports.router)
app.include_router(reclamations.router)
app.include_router(approbations.router)
app.include_router(pieces_jointes.router)
app.include_router(templates.router)
app.include_router(imap.router)
app.include_router(retention.router)
app.include_router(whatsapp.router)
app.include_router(bi.router)
app.include_router(dashboard.router)
app.include_router(exports.router)
app.include_router(agents.router)
app.include_router(cron.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="assets")

    @app.get("/")
    def index():
        return FileResponse(FRONTEND_DIR / "index.html")

    @app.get("/sw.js")
    def service_worker():
        return FileResponse(FRONTEND_DIR / "sw.js", media_type="application/javascript")

    @app.get("/manifest.json")
    def manifest():
        return FileResponse(FRONTEND_DIR / "manifest.json", media_type="application/manifest+json")

    @app.get("/{page}.html")
    def page(page: str):
        cible = FRONTEND_DIR / f"{page}.html"
        if cible.exists():
            return FileResponse(cible)
        return FileResponse(FRONTEND_DIR / "index.html")

    docs_dir = FRONTEND_DIR / "docs"
    if docs_dir.exists():
        from fastapi.staticfiles import StaticFiles as _SF
        app.mount("/docs", _SF(directory=docs_dir), name="docs")
