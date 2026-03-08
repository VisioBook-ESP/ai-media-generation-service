import json
import logging

import nats
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse

router = APIRouter()
logger = logging.getLogger(__name__)

_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>Dev — ai-media-generation-service</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: monospace; background: #0f0f0f; color: #e0e0e0; padding: 24px; }
  h1 { font-size: 16px; color: #888; margin-bottom: 24px; }
  .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; height: calc(100vh - 80px); }
  .panel { display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
  label { font-size: 12px; color: #666; display: block; margin-bottom: 4px; }
  input, textarea {
    width: 100%; background: #1a1a1a; border: 1px solid #333; color: #e0e0e0;
    padding: 8px 10px; font-family: monospace; font-size: 13px; border-radius: 4px;
  }
  input:focus, textarea:focus { outline: none; border-color: #555; }
  .row { display: flex; gap: 8px; }
  .row input { flex: 1; }
  .section-title {
    font-size: 12px; color: #555; text-transform: uppercase; letter-spacing: 1px;
    padding-bottom: 8px; border-bottom: 1px solid #222;
  }
  .item { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 4px; padding: 12px; position: relative; }
  .item button.remove {
    position: absolute; top: 8px; right: 8px; background: none; border: none;
    color: #444; cursor: pointer; font-size: 14px; padding: 2px 6px;
  }
  .item button.remove:hover { color: #c0392b; }
  button.add {
    background: none; border: 1px dashed #333; color: #555; padding: 8px;
    width: 100%; cursor: pointer; font-family: monospace; font-size: 12px; border-radius: 4px;
  }
  button.add:hover { border-color: #555; color: #888; }
  button.submit {
    background: #1d4ed8; border: none; color: white; padding: 12px;
    width: 100%; cursor: pointer; font-family: monospace; font-size: 13px;
    border-radius: 4px; margin-top: 8px;
  }
  button.submit:hover { background: #2563eb; }
  button.submit:disabled { background: #1a2a4a; color: #456; cursor: not-allowed; }
  #logs {
    flex: 1; background: #0a0a0a; border: 1px solid #222; border-radius: 4px;
    padding: 12px; overflow-y: auto; font-size: 12px; line-height: 1.6;
  }
  .log-entry { padding: 4px 0; border-bottom: 1px solid #111; }
  .log-entry .time { color: #444; margin-right: 8px; }
  .log-entry .subject { color: #3b82f6; margin-right: 8px; }
  .log-entry .data { color: #a0a0a0; white-space: pre-wrap; word-break: break-all; }
  .log-entry.sent .subject { color: #10b981; }
  .log-entry.error .subject { color: #ef4444; }
  .ws-status { font-size: 11px; color: #444; padding: 4px 0; }
  .ws-status.connected { color: #10b981; }
  .ws-status.disconnected { color: #ef4444; }
  .item-label { font-size: 11px; color: #444; margin-bottom: 8px; }
</style>
</head>
<body>
<h1>ai-media-generation-service / dev UI</h1>
<div class="layout">

  <div class="panel" id="form-panel">
    <div>
      <div class="section-title">Identifiants</div>
      <br>
      <div class="row">
        <div style="flex:1"><label>projectId</label><input id="projectId" value="test-001"></div>
        <div style="flex:1"><label>executionId</label><input id="executionId" value="exec-001"></div>
      </div>
    </div>

    <div>
      <div class="section-title">Style visuel</div>
      <br>
      <label>visualStyle</label>
      <input id="visualStyle" value="watercolor illustration, soft colors, storybook style">
      <br>
      <label>negativePrompt</label>
      <input id="negativePrompt" value="ugly, blurry, low quality">
    </div>

    <div>
      <div class="section-title">Personnages</div>
      <br>
      <div id="characters"></div>
      <button class="add" onclick="addCharacter()">+ Ajouter un personnage</button>
    </div>

    <div>
      <div class="section-title">Lieux</div>
      <br>
      <div id="locations"></div>
      <button class="add" onclick="addLocation()">+ Ajouter un lieu</button>
    </div>

    <button class="submit" id="submitBtn" onclick="send()">Publier l'event NATS</button>
  </div>

  <div class="panel">
    <div class="section-title">Logs NATS en temps réel</div>
    <div class="ws-status disconnected" id="wsStatus">● WebSocket déconnecté</div>
    <div id="logs"></div>
  </div>

</div>

<script>
let charCount = 0, locCount = 0;

function addCharacter(id='', desc='') {
  charCount++;
  const n = charCount;
  const div = document.createElement('div');
  div.className = 'item';
  div.id = 'char-' + n;
  div.innerHTML = `
    <div class="item-label">Personnage #${n}</div>
    <button class="remove" onclick="this.parentElement.remove()">✕</button>
    <label>characterId</label>
    <input class="char-id" value="${id || 'char-' + n}" style="margin-bottom:8px">
    <label>physicalDescription</label>
    <input class="char-desc" value="${desc}">
  `;
  document.getElementById('characters').appendChild(div);
}

function addLocation(id='', desc='') {
  locCount++;
  const n = locCount;
  const div = document.createElement('div');
  div.className = 'item';
  div.id = 'loc-' + n;
  div.innerHTML = `
    <div class="item-label">Lieu #${n}</div>
    <button class="remove" onclick="this.parentElement.remove()">✕</button>
    <label>locationId</label>
    <input class="loc-id" value="${id || 'loc-' + n}" style="margin-bottom:8px">
    <label>description</label>
    <input class="loc-desc" value="${desc}">
  `;
  document.getElementById('locations').appendChild(div);
}

async function send() {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  btn.textContent = 'Envoi...';

  const characters = [...document.querySelectorAll('#characters .item')].map(el => ({
    characterId: el.querySelector('.char-id').value,
    physicalDescription: el.querySelector('.char-desc').value,
  }));

  const locations = [...document.querySelectorAll('#locations .item')].map(el => ({
    locationId: el.querySelector('.loc-id').value,
    description: el.querySelector('.loc-desc').value,
  }));

  const payload = {
    projectId: document.getElementById('projectId').value,
    executionId: document.getElementById('executionId').value,
    bookStyle: {
      visualStyle: document.getElementById('visualStyle').value,
      negativePrompt: document.getElementById('negativePrompt').value,
    },
    characters,
    locations,
  };

  try {
    const res = await fetch('/dev/publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    appendLog('sent', 'visiobook.media.generate_references', payload);
  } catch (e) {
    appendLog('error', 'ERROR', { message: e.message });
  }

  btn.disabled = false;
  btn.textContent = 'Publier l\\'event NATS';
}

function appendLog(type, subject, data) {
  const logs = document.getElementById('logs');
  const el = document.createElement('div');
  el.className = 'log-entry ' + type;
  const time = new Date().toLocaleTimeString('fr-FR', { hour12: false });
  el.innerHTML = `<span class="time">${time}</span><span class="subject">${subject}</span><br><span class="data">${JSON.stringify(data, null, 2)}</span>`;
  logs.appendChild(el);
  logs.scrollTop = logs.scrollHeight;
}

// WebSocket
function connectWS() {
  const ws = new WebSocket('ws://' + location.host + '/dev/ws');
  const status = document.getElementById('wsStatus');

  ws.onopen = () => {
    status.className = 'ws-status connected';
    status.textContent = '● WebSocket connecté';
  };

  ws.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    appendLog('', msg.subject, msg.data);
  };

  ws.onclose = () => {
    status.className = 'ws-status disconnected';
    status.textContent = '● WebSocket déconnecté — reconnexion dans 3s...';
    setTimeout(connectWS, 3000);
  };
}

// Init
addCharacter('char-1', 'A young woman with red hair and green eyes, wearing a blue dress');
connectWS();
</script>
</body>
</html>"""


@router.get("/dev", response_class=HTMLResponse)
async def dev_ui():
    return _HTML


@router.post("/dev/publish")
async def dev_publish(request: Request):
    body = await request.json()
    publisher = request.app.state.publisher
    await publisher.publish("visiobook.media.generate_references", body)
    return {"status": "ok"}


@router.websocket("/dev/ws")
async def dev_ws(websocket: WebSocket):
    await websocket.accept()
    settings = websocket.app.state.settings
    nc = await nats.connect(settings.NATS_URL)

    async def on_message(msg):
        try:
            await websocket.send_text(json.dumps({
                "subject": msg.subject,
                "data": json.loads(msg.data),
            }))
        except Exception:
            pass

    sub = await nc.subscribe("visiobook.>", cb=on_message)

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await sub.unsubscribe()
        await nc.drain()
