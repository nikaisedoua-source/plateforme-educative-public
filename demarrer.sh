#!/usr/bin/env bash
# Lance la plateforme en local : API FastAPI (port 8000) + Flutter web (port 8080).
# Usage : ./demarrer.sh   puis ouvrir http://localhost:8080   (Ctrl+C pour tout arrêter)
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/flutter/bin:/opt/homebrew/bin:$PATH"

# Disque exFAT : supprimer les fichiers fantômes ._* qui cassent Python/Alembic
dot_clean -m "$ROOT/backend" "$ROOT/frontend" 2>/dev/null || true

pg_isready -q || { echo "PostgreSQL ne répond pas : brew services start postgresql@18"; exit 1; }

cd "$ROOT/backend"
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload &
API_PID=$!
trap 'kill $API_PID 2>/dev/null' EXIT

cd "$ROOT/frontend"
flutter run -d web-server --web-hostname localhost --web-port 8080 \
  --dart-define=API_BASE_URL=http://localhost:8000
