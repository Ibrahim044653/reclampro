"""Point d'entrée FastAPI — lance avec : uvicorn app.main:app --reload"""
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import CORS_ORIGINS
from .database import Base, engine
from .routers import (
    reclamations, dashboard, exports, agents, auth, users,
    equipes, notifications, reports, pieces_jointes, public,
    templates, approbations, imap, retention, whatsapp, bi,
)

try:
    Base.metadata.create_all(bind=engine)
except Exception as _db_err:
    import logging
    logging.getLogger(__name__).error("DB init error: %s", _db_err)

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
