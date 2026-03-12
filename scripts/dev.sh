#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

cleanup() {
    trap - EXIT INT TERM
    echo ""
    echo "Arrêt..."
    docker stop nats-dev > /dev/null 2>&1 || true
    kill "$NGROK_PID" "$SERVER_PID" 2>/dev/null || true
    wait "$NGROK_PID" "$SERVER_PID" 2>/dev/null || true
    echo "Done."
}
trap cleanup EXIT INT TERM

# ── 1. NATS ──────────────────────────────────────────────────────────────────

echo "[1/3] Démarrage NATS..."
if docker ps --filter "publish=4222" --format "{{.ID}}" | grep -q .; then
    echo "  NATS déjà en cours"
else
    docker run -d --rm -p 4222:4222 --name nats-dev nats:latest -js > /dev/null
fi
NATS_PID=$(docker inspect --format '{{.State.Pid}}' nats-dev 2>/dev/null || echo 0)

# ── 2. ngrok ─────────────────────────────────────────────────────────────────

echo "[2/3] Démarrage ngrok..."
ngrok http 8087 --log=stdout > /tmp/ngrok.log 2>&1 &
NGROK_PID=$!

sleep 2

NGROK_URL=$(curl -s http://127.0.0.1:4040/api/tunnels | python3 -c \
    "import sys,json; print(json.load(sys.stdin)['tunnels'][0]['public_url'])" 2>/dev/null || echo "")

if [[ -z "$NGROK_URL" ]]; then
    echo "  Erreur : impossible de récupérer l'URL ngrok"
    exit 1
fi

echo "  URL ngrok : $NGROK_URL"

# Mettre à jour .env
sed -i "s|WEBHOOK_BASE_URL=.*|WEBHOOK_BASE_URL=$NGROK_URL|" "$ROOT/.env"
echo "  .env mis à jour"

# ── 3. Serveur ───────────────────────────────────────────────────────────────

echo "[3/3] Démarrage du serveur..."
fuser -k 8087/tcp > /dev/null 2>&1 || true
cd "$ROOT"
.venv/bin/uvicorn app.main:app --port 8087 --reload &
SERVER_PID=$!

sleep 2

echo ""
echo "✓ Tout est démarré"
echo "  Dev UI  : http://localhost:8087/dev"
echo "  ngrok   : $NGROK_URL"
echo ""
echo "Ctrl+C pour tout arrêter"

wait "$SERVER_PID"
