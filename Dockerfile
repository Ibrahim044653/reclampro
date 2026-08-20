# syntax=docker/dockerfile:1.7
# Image multi-stage : builder pour les dépendances Python, runtime mince pour la prod.
# Contexte de build : racine du projet (pour avoir accès à backend/ ET frontend/).

# ---------- Stage 1 : Builder ----------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Dépendances système pour cryptography / psycopg
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt .

# Venv isolé pour copier proprement vers le runtime + psycopg pour PostgreSQL
RUN python -m venv /venv && \
    /venv/bin/pip install --upgrade pip && \
    /venv/bin/pip install -r requirements.txt && \
    /venv/bin/pip install "psycopg[binary]>=3.2"


# ---------- Stage 2 : Runtime ----------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/venv/bin:$PATH"

# Bibliothèques système d'exécution
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

# Utilisateur non-root pour la sécurité
RUN useradd --create-home --uid 1000 app

WORKDIR /app

COPY --from=builder /venv /venv
COPY --chown=app:app backend /app/backend
COPY --chown=app:app frontend /app/frontend

# Crée le répertoire uploads avec les bons droits
RUN mkdir -p /app/backend/uploads && chown -R app:app /app/backend/uploads

USER app
WORKDIR /app/backend

VOLUME ["/app/backend/uploads"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/api/health || exit 1

EXPOSE 8000

ENTRYPOINT ["/app/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
