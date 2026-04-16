import asyncio
import json
import logging
import time
from collections import deque

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

router = APIRouter(prefix="/dev", tags=["dev"])
logger = logging.getLogger(__name__)

# In-memory event buffer for the dev UI
_events: deque = deque(maxlen=200)
_event_counter = 0
_subscriber_task = None


async def start_event_listener(nats_url: str, stream: str):
    """Subscribe to visiobook.ai.> and buffer events for the dev UI."""
    import nats as nats_client
    global _subscriber_task

    async def _listen():
        global _event_counter
        nc = await nats_client.connect(nats_url)
        js = nc.jetstream()
        sub = await js.subscribe("visiobook.ai.>", stream=stream, ordered_consumer=True)
        async for msg in sub.messages:
            _event_counter += 1
            try:
                data = json.loads(msg.data)
            except Exception:
                data = msg.data.decode(errors="replace")
            _events.append({"id": _event_counter, "ts": time.time() * 1000, "subject": msg.subject, "data": data})
            await msg.ack()

    _subscriber_task = asyncio.create_task(_listen())


@router.get("/events")
async def get_events(after: int = Query(0)):
    """Return buffered NATS events after a given ID."""
    return [e for e in _events if e["id"] > after]


@router.post("/generate")
async def trigger_generate(request: Request):
    """Publish a pipeline message to NATS for testing."""
    body = await request.json()
    publisher = request.app.state.publisher
    await publisher.publish("visiobook.media.generate", body)
    return {"status": "published", "projectId": body.get("projectId")}


@router.get("/", response_class=HTMLResponse)
async def dev_ui():
    return _HTML


_EXAMPLE = {
    "projectId": "test-project",
    "executionId": "test-exec-1",
    "userId": "test-user",
    "characters": [
        {
            "name": "Luna",
            "description": "petite fille curieuse de 8 ans, aventuriere dans un monde magique",
            "physicalDescription": "8-year-old girl, big round brown eyes, wavy chestnut hair with a small braid, rosy cheeks, small nose",
            "portraitPrompt": "children's storybook illustration, a cute 8-year-old girl with big round brown eyes, wavy chestnut hair with a small braid tied with a golden ribbon, rosy cheeks, wearing a cozy oversized dark green knitted sweater, a little brown leather satchel across her shoulder, red rain boots, full body character reference sheet, standing pose, entire body visible from head to toe, simple soft pastel background, front view, warm soft lighting, watercolor and gouache painting style, whimsical, detailed, Pixar-inspired character design",
            "portraitNegativePrompt": "realistic, photographic, multiple people, adult, scary, dark, horror, blurry, bad anatomy, extra limbs, extra fingers",
        },
        {
            "name": "Monsieur Hibou",
            "description": "vieux hibou sage et bienveillant, guide de Luna",
            "physicalDescription": "old wise owl, large golden eyes, brown and cream feathers, small round spectacles on beak",
            "portraitPrompt": "children's storybook illustration, a charming old wise owl with large expressive golden eyes, round tiny spectacles perched on his beak, fluffy brown and cream feathers with speckled patterns, a tiny red bowtie around his neck, perched on a branch, full body character reference sheet, front view, simple soft pastel background, warm soft lighting, watercolor and gouache painting style, whimsical, cute, Pixar-inspired character design",
            "portraitNegativePrompt": "realistic, photographic, scary, dark, horror, blurry, multiple characters",
        },
    ],
    "locations": [
        {
            "locationId": "enchanted_forest",
            "name": "La Foret Enchantee",
            "descriptionPrompt": "children's storybook illustration, enchanted magical forest, giant ancient trees with twisting trunks covered in soft green moss, glowing mushrooms in warm orange and blue, tiny floating fireflies and sparkles, a winding cobblestone path disappearing into the trees, dappled golden sunlight filtering through the canopy, colorful wildflowers along the path, whimsical atmosphere, watercolor and gouache painting style, warm color palette, soft lighting, wide angle establishing shot, no characters, highly detailed background art",
            "negativePrompt": "people, characters, text, realistic, photographic, dark, horror, scary",
            "sourceSceneOrders": [0, 1],
        },
        {
            "locationId": "crystal_lake",
            "name": "Le Lac de Cristal",
            "descriptionPrompt": "children's storybook illustration, magical crystal-clear lake surrounded by weeping willows, perfectly still turquoise water reflecting a pastel pink and orange sunset sky, smooth round stones along the shore, lily pads with tiny glowing flowers, a small wooden dock extending into the water, distant rolling green hills, a few fluffy clouds, peaceful serene atmosphere, watercolor and gouache painting style, warm golden hour lighting, wide angle, no characters, highly detailed background art",
            "negativePrompt": "people, characters, text, realistic, photographic, dark, horror, night",
            "sourceSceneOrders": [2],
        },
    ],
    "scenes": [
        {
            "order": 0,
            "text": "Luna poussa la vieille porte en bois et decouvrit un sentier lumineux qui s'enfoncait dans la Foret Enchantee...",
            "description": "Decouverte de la foret enchantee",
            "imagePrompt": "children's storybook illustration, a cute 8-year-old girl with wavy chestnut hair and green sweater pushing open an old wooden gate, discovering a magical glowing cobblestone path leading into an enchanted forest, giant mossy trees with twisting trunks, glowing mushrooms and floating fireflies, golden sunlight streaming through the canopy, sense of wonder and adventure, watercolor and gouache painting style, warm soft lighting, whimsical, cinematic composition, wide shot",
            "negativePrompt": "realistic, photographic, dark, horror, scary, bad anatomy, extra limbs, adult",
            "duration": 5,
            "sentiment": "wonder",
            "charactersPresent": ["Luna"],
            "locationId": "enchanted_forest",
        },
        {
            "order": 1,
            "text": "Monsieur Hibou descendit de sa branche et se posa delicatement sur l'epaule de Luna. 'Bienvenue, petite exploratrice', murmura-t-il.",
            "description": "Rencontre avec Monsieur Hibou",
            "imagePrompt": "children's storybook illustration, a cute 8-year-old girl with wavy chestnut hair and green sweater looking up with big amazed eyes as a charming old owl with round spectacles and a red bowtie gently lands on her shoulder, enchanted forest background with glowing mushrooms and fireflies, warm golden dappled light, magical sparkles around them, tender heartwarming moment, watercolor and gouache painting style, medium close-up shot, warm soft lighting, whimsical",
            "negativePrompt": "realistic, photographic, dark, horror, scary, bad anatomy, extra limbs, adult",
            "duration": 4,
            "sentiment": "tenderness",
            "charactersPresent": ["Luna", "Monsieur Hibou"],
            "locationId": "enchanted_forest",
        },
        {
            "order": 2,
            "text": "Ensemble, ils arriverent au Lac de Cristal. La surface de l'eau brillait comme un miroir magique, refletant un ciel aux mille couleurs...",
            "description": "Arrivee au Lac de Cristal",
            "imagePrompt": "children's storybook illustration, a cute 8-year-old girl with wavy chestnut hair and green sweater standing at the edge of a magical crystal-clear turquoise lake at golden hour, an old owl with spectacles perched on her shoulder, both gazing at the perfectly still water reflecting a beautiful pastel pink and orange sunset, weeping willows framing the scene, glowing lily pads, smooth stones on the shore, peaceful magical atmosphere, watercolor and gouache painting style, wide cinematic composition, warm golden lighting, whimsical, masterpiece",
            "negativePrompt": "realistic, photographic, dark, horror, scary, bad anatomy, extra limbs, adult, night",
            "duration": 5,
            "sentiment": "peaceful",
            "charactersPresent": ["Luna", "Monsieur Hibou"],
            "locationId": "crystal_lake",
        },
    ],
    "correlationId": "test-corr-1",
}

_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Visiobook Media — Dev Console</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
         background: #0d1117; color: #c9d1d9; padding: 24px; }
  h1 { font-size: 1.3rem; margin-bottom: 16px; color: #58a6ff; }
  .layout { display: flex; gap: 16px; height: calc(100vh - 80px); }
  .panel { flex: 1; display: flex; flex-direction: column; }
  label { font-size: 0.8rem; color: #8b949e; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
  textarea { flex: 1; background: #161b22; color: #c9d1d9; border: 1px solid #30363d;
             border-radius: 6px; padding: 12px; font-family: monospace; font-size: 0.85rem;
             resize: none; outline: none; }
  textarea:focus { border-color: #58a6ff; }
  .actions { margin-top: 8px; display: flex; gap: 8px; align-items: center; }
  button { background: #238636; color: #fff; border: none; border-radius: 6px;
           padding: 8px 20px; font-size: 0.85rem; cursor: pointer; font-weight: 600; }
  button:hover { background: #2ea043; }
  button:disabled { opacity: 0.5; cursor: not-allowed; }
  button.secondary { background: #30363d; }
  button.secondary:hover { background: #484f58; }
  .status { font-size: 0.8rem; color: #8b949e; }
  .status.ok { color: #3fb950; }
  .status.err { color: #f85149; }
  #logs { background: #0d1117; border: 1px solid #30363d; font-size: 0.8rem; color: #8b949e; }
  .log-entry { padding: 2px 0; border-bottom: 1px solid #21262d; }
  .log-entry .time { color: #484f58; }
  .log-entry .subject { color: #d2a8ff; }
  .log-entry .body { color: #c9d1d9; }
</style>
</head>
<body>
<h1>Visiobook Media — Dev Console</h1>
<div class="layout">
  <div class="panel">
    <label>Message JSON</label>
    <textarea id="payload" spellcheck="false">""" + json.dumps(_EXAMPLE, indent=2, ensure_ascii=False) + """</textarea>
    <div class="actions">
      <button id="sendBtn" onclick="send()">Envoyer</button>
      <button class="secondary" onclick="resetExample()">Reset exemple</button>
      <button class="secondary" onclick="checkHealth()">Health check</button>
      <span id="status" class="status"></span>
    </div>
  </div>
  <div class="panel">
    <label>Events NATS (live)</label>
    <textarea id="logs" readonly></textarea>
    <div class="actions">
      <button class="secondary" onclick="clearLogs()">Clear</button>
      <span style="font-size:0.75rem;color:#484f58">Auto-refresh toutes les 2s</span>
    </div>
  </div>
</div>
<script>
const example = """ + json.dumps(_EXAMPLE, ensure_ascii=False) + """;

async function send() {
  const btn = document.getElementById('sendBtn');
  const status = document.getElementById('status');
  btn.disabled = true;
  status.className = 'status';
  status.textContent = 'Envoi...';
  try {
    let payload;
    try { payload = JSON.parse(document.getElementById('payload').value); }
    catch(e) { throw new Error('JSON invalide: ' + e.message); }
    const r = await fetch('/dev/generate', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    const data = await r.json();
    if (r.ok) { status.className = 'status ok'; status.textContent = 'Publie — ' + data.projectId; }
    else { throw new Error(data.detail || r.statusText); }
  } catch(e) { status.className = 'status err'; status.textContent = e.message; }
  finally { btn.disabled = false; }
}

function resetExample() {
  document.getElementById('payload').value = JSON.stringify(example, null, 2);
  document.getElementById('status').textContent = '';
}

async function checkHealth() {
  const status = document.getElementById('status');
  try {
    const r = await fetch('/health');
    const data = await r.json();
    status.className = data.status === 'ok' ? 'status ok' : 'status err';
    status.textContent = JSON.stringify(data);
  } catch(e) { status.className = 'status err'; status.textContent = e.message; }
}

function clearLogs() { document.getElementById('logs').value = ''; }

// Poll events from server
let lastEventId = 0;
async function pollEvents() {
  try {
    const r = await fetch('/dev/events?after=' + lastEventId);
    const events = await r.json();
    const logs = document.getElementById('logs');
    for (const ev of events) {
      const time = new Date(ev.ts).toLocaleTimeString();
      logs.value += '[' + time + '] ' + ev.subject + '\\n' + JSON.stringify(ev.data, null, 2) + '\\n\\n';
      lastEventId = ev.id;
    }
    if (events.length) logs.scrollTop = logs.scrollHeight;
  } catch(e) {}
}
setInterval(pollEvents, 2000);
</script>
</body>
</html>
"""
