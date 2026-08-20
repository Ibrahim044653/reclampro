#!/bin/sh
# Entrypoint Docker — attend la DB si configurée, applique les migrations,
# seed optionnellement, puis lance la commande passée en argument.

set -e

# Attente de la base de données si DATABASE_URL est un PostgreSQL distant
if echo "$DATABASE_URL" | grep -q "^postgresql"; then
    echo "[entrypoint] Attente de PostgreSQL..."
    HOST=$(echo "$DATABASE_URL" | sed -E 's|.*@([^:/]+).*|\1|')
    PORT=$(echo "$DATABASE_URL" | sed -E 's|.*:([0-9]+)/.*|\1|')
    PORT=${PORT:-5432}
    for i in $(seq 1 30); do
        if python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('$HOST', $PORT)); s.close()" 2>/dev/null; then
            echo "[entrypoint] PostgreSQL disponible sur $HOST:$PORT"
            break
        fi
        echo "[entrypoint] Tentative $i/30..."
        sleep 1
    done
fi

# Création des tables (SQLAlchemy create_all idempotent)
python -c "from app.database import Base, engine; from app import models; Base.metadata.create_all(bind=engine)" \
    && echo "[entrypoint] Schéma DB OK"

# Seed automatique si SEED_AT_STARTUP=true ET base vide
if [ "${SEED_AT_STARTUP:-false}" = "true" ]; then
    NB_AGENTS=$(python -c "from app.database import SessionLocal; from app import models; s=SessionLocal(); print(s.query(models.Agent).count()); s.close()" 2>/dev/null || echo 0)
    if [ "$NB_AGENTS" = "0" ]; then
        echo "[entrypoint] Base vide — exécution du seed..."
        python -m app.seed
    else
        echo "[entrypoint] Base déjà peuplée ($NB_AGENTS agents) — pas de seed"
    fi
fi

exec "$@"
