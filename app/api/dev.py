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
            "name": "Kael",
            "description": "jeune pilote rebelle, cicatrice sur la joue gauche, regard determine",
            "physicalDescription": "young man, short silver-white hair, sharp grey eyes, angular jaw, thin scar across left cheek, lean athletic build",
            "portraitPrompt": "young man with short silver-white hair, sharp grey eyes, thin scar across left cheek, wearing a dark fitted flight suit with glowing cyan circuit patterns, armored shoulder pads, utility belt with holographic tools, full body character reference, standing pose, entire body visible from head to toe, neutral dark background, front view, highly detailed, sci-fi character concept art, cinematic lighting",
            "portraitNegativePrompt": "multiple people, blurry, bad anatomy, extra limbs, medieval, fantasy",
        }
    ],
    "locations": [
        {
            "locationId": "orbital_station",
            "name": "Station orbitale Zenith",
            "descriptionPrompt": "massive orbital space station interior, vast observation deck with panoramic windows showing planet Earth below, sleek metallic walls with embedded holographic displays, floating data screens, ambient blue and cyan neon lighting, zero-gravity plants in glass pods, reflective floors, ultra futuristic architecture, environment concept art, wide angle establishing shot, no characters, highly detailed, 8k",
            "negativePrompt": "people, characters, text, medieval, fantasy, trees, nature",
            "sourceSceneOrders": [0, 1],
        },
        {
            "locationId": "neon_city",
            "name": "Secteur Bas de Neo-Osaka",
            "descriptionPrompt": "cyberpunk lower city streets at night, towering megastructures, dense neon signs in Japanese and holographic advertisements, rain-slicked streets reflecting pink and blue neon, steam rising from vents, flying vehicles in the distance, narrow alleyways with market stalls, dark moody atmosphere, environment concept art, wide angle, no characters, cinematic, 8k",
            "negativePrompt": "people, characters, text, daylight, nature, medieval",
            "sourceSceneOrders": [2],
        },
    ],
    "scenes": [
        {
            "order": 0,
            "text": "Kael observait la Terre depuis le pont d'observation, les lumieres des villes scintillant comme des constellations inversees...",
            "description": "Contemplation depuis la station orbitale",
            "imagePrompt": "young man with short silver-white hair and glowing cyan flight suit standing at massive panoramic window of orbital space station, gazing down at planet Earth glowing blue below, holographic displays floating around him, ambient blue neon lighting, reflective metallic floor, cinematic composition, dramatic lighting, sci-fi concept art, 8k, masterpiece",
            "negativePrompt": "bad anatomy, extra limbs, blurry, low quality, medieval, fantasy",
            "duration": 5,
            "sentiment": "contemplative",
            "charactersPresent": ["Kael"],
            "locationId": "orbital_station",
        },
        {
            "order": 1,
            "text": "L'alarme retentit. Les ecrans holographiques virerent au rouge, affichant des trajectoires d'interception...",
            "description": "Alerte sur la station",
            "imagePrompt": "young man with silver-white hair running through orbital station corridor, red emergency lights flashing, holographic warning screens displaying threat trajectories in red, sparks flying from damaged panels, dramatic motion blur, urgent atmosphere, cinematic sci-fi action scene, volumetric red lighting, 8k",
            "negativePrompt": "bad anatomy, extra limbs, blurry, calm scene, medieval, fantasy",
            "duration": 4,
            "sentiment": "urgent",
            "charactersPresent": ["Kael"],
            "locationId": "orbital_station",
        },
        {
            "order": 2,
            "text": "Il plongea dans les ruelles du Secteur Bas, ou les neons masquaient les ombres et les secrets...",
            "description": "Fuite dans Neo-Osaka",
            "imagePrompt": "young man with silver-white hair in dark flight suit walking through narrow cyberpunk alley at night, towering neon signs in Japanese glowing pink and blue, rain-slicked ground with reflections, steam rising from vents, holographic advertisements overhead, moody cinematic atmosphere, volumetric fog, cyberpunk noir, 8k, masterpiece",
            "negativePrompt": "bad anatomy, extra limbs, blurry, daylight, bright cheerful, medieval, fantasy",
            "duration": 5,
            "sentiment": "tense",
            "charactersPresent": ["Kael"],
            "locationId": "neon_city",
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
