#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
    trap - EXIT INT TERM
    echo ""
    echo "Arrêt..."
    docker stop nats-dev > /dev/null 2>&1 || true
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# ── 1. NATS ──────────────────────────────────────────────────────────────────

echo "[1/2] Démarrage NATS..."
if docker ps --filter "publish=4222" --format "{{.ID}}" | grep -q .; then
    echo "  NATS déjà en cours"
else
    docker run -d --rm -p 4222:4222 --name nats-dev nats:latest -js > /dev/null
fi

# ── 2. Serveur ───────────────────────────────────────────────────────────────

echo "[2/2] Démarrage du serveur..."
fuser -k 8087/tcp > /dev/null 2>&1 || true
cd "$ROOT"
.venv/bin/uvicorn app.main:app --port 8087 --reload &
SERVER_PID=$!

sleep 2

echo ""
echo "Tout est demarré"
echo "  Dev UI   : http://localhost:8087/dev"
echo "  ComfyUI  : $(.venv/bin/python -c "from app.config import Settings; print(Settings().COMFYUI_URL)" 2>/dev/null || echo '(voir .env)')"
echo ""
echo "Ctrl+C pour tout arrêter"

wait "$SERVER_PID"
