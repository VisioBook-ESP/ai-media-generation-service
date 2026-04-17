#!/usr/bin/env bash
set -euo pipefail

# ── Configuration ───────────────────────────────────────────────────────────
BASE_URL="${1:-http://visiobook.cloud:30090}"
BASE_URL="${BASE_URL%/}"

# ── Couleurs ────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# ── 1. Health check ────────────────────────────────────────────────────────
echo -e "${CYAN}[1/3] Health check ($BASE_URL)...${NC}"
HEALTH=$(curl -s --max-time 5 "$BASE_URL/health" 2>/dev/null || echo '{"error":"connection refused"}')
echo "  $HEALTH"

STATUS=$(echo "$HEALTH" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
if [ "$STATUS" != "ok" ]; then
    echo -e "${RED}  Service pas healthy. Vérifiez les logs du pod.${NC}"
    exit 1
fi
echo -e "${GREEN}  Service healthy${NC}"

# ── 2. Envoi du message de test ────────────────────────────────────────────
echo ""
echo -e "${CYAN}[2/3] Envoi du pipeline de test (Luna, 1 scène)...${NC}"

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/dev/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "projectId": "test-project",
    "executionId": "test-exec-prod-1",
    "userId": "test-user",
    "characters": [
        {
            "name": "Luna",
            "description": "petite fille curieuse de 8 ans",
            "physicalDescription": "8-year-old girl, big round brown eyes, wavy chestnut hair with a small braid, rosy cheeks",
            "portraitPrompt": "children'\''s storybook illustration, a cute 8-year-old girl with big round brown eyes, wavy chestnut hair with a small braid tied with a golden ribbon, rosy cheeks, wearing a cozy oversized dark green knitted sweater, a little brown leather satchel across her shoulder, red rain boots, full body character reference sheet, standing pose, entire body visible from head to toe, simple soft pastel background, front view, warm soft lighting, watercolor and gouache painting style, whimsical, detailed, Pixar-inspired character design",
            "portraitNegativePrompt": "realistic, photographic, multiple people, adult, scary, dark, horror, blurry, bad anatomy, extra limbs"
        }
    ],
    "locations": [
        {
            "locationId": "enchanted_forest",
            "name": "La Foret Enchantee",
            "descriptionPrompt": "children'\''s storybook illustration, enchanted magical forest, giant ancient trees with twisting trunks covered in soft green moss, glowing mushrooms, floating fireflies, winding cobblestone path, dappled golden sunlight, watercolor and gouache painting style, warm color palette, wide angle, no characters",
            "negativePrompt": "people, characters, text, realistic, photographic, dark, horror",
            "sourceSceneOrders": [0]
        }
    ],
    "scenes": [
        {
            "order": 0,
            "text": "Luna poussa la vieille porte en bois et découvrit un sentier lumineux...",
            "description": "Découverte de la forêt enchantée",
            "imagePrompt": "children'\''s storybook illustration, a cute 8-year-old girl with wavy chestnut hair and green sweater pushing open an old wooden gate, discovering a magical glowing cobblestone path leading into an enchanted forest, giant mossy trees, glowing mushrooms and floating fireflies, golden sunlight, watercolor and gouache painting style, warm soft lighting, whimsical, cinematic composition",
            "negativePrompt": "realistic, photographic, dark, horror, scary, bad anatomy, extra limbs, adult",
            "duration": 5,
            "sentiment": "wonder",
            "charactersPresent": ["Luna"],
            "locationId": "enchanted_forest"
        }
    ],
    "correlationId": "test-prod-1"
  }')

HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [ "$HTTP_CODE" = "200" ]; then
    echo -e "${GREEN}  Message publié avec succès${NC}"
    echo "  $BODY"
else
    echo -e "${RED}  Erreur HTTP $HTTP_CODE${NC}"
    echo "  $BODY"
    exit 1
fi

# ── 3. Suivi des events en live ────────────────────────────────────────────
echo ""
echo -e "${CYAN}[3/3] Suivi des events NATS en live (Ctrl+C pour quitter)...${NC}"
echo ""

LAST_ID=0
while true; do
    EVENTS=$(curl -s "$BASE_URL/dev/events?after=$LAST_ID" 2>/dev/null || echo "[]")
    COUNT=$(echo "$EVENTS" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo "0")

    if [ "$COUNT" -gt "0" ]; then
        echo "$EVENTS" | python3 -c "
import sys, json
from datetime import datetime
events = json.load(sys.stdin)
for e in events:
    ts = datetime.fromtimestamp(e['ts']/1000).strftime('%H:%M:%S')
    subj = e['subject']
    data = e.get('data', {})

    if 'completed' in subj:
        color = '\033[0;32m'
    elif 'failed' in subj:
        color = '\033[0;31m'
    elif 'progress' in subj:
        color = '\033[0;33m'
    else:
        color = '\033[0;36m'

    print(f'{color}[{ts}] {subj}\033[0m')
    if 'progress' in data:
        print(f'         {data.get(\"step\",\"\")} — {data.get(\"progress\",0)}% — {data.get(\"message\",\"\")}')
    elif 'error' in data:
        print(f'         ERROR: {data[\"error\"]}')
    elif 'mediaUrl' in data:
        print(f'         -> {data[\"mediaUrl\"]}')
    elif 'referenceImageUrl' in data:
        print(f'         -> {data[\"referenceImageUrl\"]}')
"
        LAST_ID=$(echo "$EVENTS" | python3 -c "import sys,json; print(max(e['id'] for e in json.load(sys.stdin)))" 2>/dev/null || echo "$LAST_ID")
    fi

    if echo "$EVENTS" | grep -q "pipeline.completed" 2>/dev/null; then
        echo ""
        echo -e "${GREEN}Pipeline terminé !${NC}"
        break
    fi

    sleep 2
done
