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
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dev UI</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #f5f6f8;
    --surface: #ffffff;
    --surface2: #f0f1f4;
    --border: #e2e4ea;
    --text: #1a1d27;
    --text-muted: #8b8fa8;
    --accent: #5b5ef4;
    --accent-hover: #4244d4;
    --accent-light: #eeeeff;
    --green: #16a34a;
    --green-bg: #f0fdf4;
    --red: #dc2626;
    --red-bg: #fef2f2;
    --blue: #2563eb;
    --blue-bg: #eff6ff;
  }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'Segoe UI', sans-serif;
    background: var(--bg); color: var(--text);
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 24px; height: 52px; border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .header-left { display: flex; align-items: center; gap: 8px; }
  .header-logo {
    width: 22px; height: 22px; background: var(--accent); border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
  }
  .header-logo svg { width: 12px; height: 12px; fill: white; }
  header h1 { font-size: 13px; font-weight: 600; color: var(--text); }
  header h1 span { color: var(--text-muted); font-weight: 400; }
  .badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 11px; font-weight: 500; padding: 3px 8px; border-radius: 100px;
    border: 1px solid var(--border); color: var(--text-muted); background: var(--surface2);
  }
  .badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); }
  .badge.connected { border-color: #bbf7d0; color: var(--green); background: var(--green-bg); }
  .badge.connected::before { background: var(--green); }
  .badge.disconnected { border-color: #fecaca; color: var(--red); background: var(--red-bg); }
  .badge.disconnected::before { background: var(--red); }
  .main { display: grid; grid-template-columns: 380px 1fr; flex: 1; overflow: hidden; }
  .sidebar {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--border); overflow-y: auto;
    background: var(--surface);
  }
  .section { padding: 18px 20px; border-bottom: 1px solid var(--border); }
  .section-label {
    font-size: 11px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.7px; color: var(--text-muted); margin-bottom: 14px;
  }
  label { font-size: 12px; font-weight: 500; color: var(--text-muted); display: block; margin-bottom: 4px; }
  input, textarea {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 7px 10px; font-size: 13px; border-radius: 7px;
    transition: border-color 0.15s, box-shadow 0.15s;
    font-family: inherit;
  }
  input:focus, textarea:focus {
    outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 3px var(--accent-light);
  }
  .row { display: flex; gap: 10px; }
  .row > * { flex: 1; }
  .field { margin-bottom: 10px; }
  .field:last-child { margin-bottom: 0; }
  .card {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 8px; padding: 12px 14px; margin-bottom: 8px; position: relative;
  }
  .card-title { font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
  .btn-remove {
    position: absolute; top: 10px; right: 10px; background: none; border: none;
    color: var(--text-muted); cursor: pointer; font-size: 15px; line-height: 1;
    padding: 2px 5px; border-radius: 4px; transition: all 0.15s;
  }
  .btn-remove:hover { color: var(--red); background: var(--red-bg); }
  .btn-add {
    width: 100%; background: none; border: 1px dashed var(--border);
    color: var(--text-muted); padding: 8px; cursor: pointer;
    font-size: 12px; font-weight: 500; border-radius: 7px; transition: all 0.15s;
    font-family: inherit;
  }
  .btn-add:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }
  .btn-submit {
    margin: 16px 20px; background: var(--accent); border: none; color: white;
    padding: 10px 20px; cursor: pointer; font-size: 13px; font-weight: 600;
    border-radius: 8px; width: calc(100% - 40px); transition: background 0.15s;
    font-family: inherit; letter-spacing: 0.1px;
  }
  .btn-submit:hover { background: var(--accent-hover); }
  .btn-submit:disabled { background: var(--surface2); color: var(--text-muted); cursor: not-allowed; }
  .logs-panel {
    display: flex; flex-direction: column; overflow: hidden; background: var(--bg);
  }
  .logs-header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 20px; height: 48px; border-bottom: 1px solid var(--border);
    background: var(--surface);
  }
  .logs-header span { font-size: 12px; font-weight: 600; color: var(--text); }
  .btn-clear {
    background: none; border: 1px solid var(--border); color: var(--text-muted);
    padding: 4px 10px; cursor: pointer; font-size: 11px; font-weight: 500;
    border-radius: 6px; transition: all 0.15s; font-family: inherit;
  }
  .btn-clear:hover { border-color: var(--text-muted); color: var(--text); }
  #logs { flex: 1; overflow-y: auto; padding: 12px 16px; font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace; }
  .log-entry {
    display: flex; gap: 12px; padding: 9px 12px; border-radius: 7px;
    margin-bottom: 4px; font-size: 12px; align-items: flex-start;
    border: 1px solid transparent; transition: background 0.1s;
  }
  .log-entry:hover { background: var(--surface); }
  .log-entry.sent { border-color: #bbf7d0; background: var(--green-bg); }
  .log-entry.error { border-color: #fecaca; background: var(--red-bg); }
  .log-time { color: var(--text-muted); white-space: nowrap; font-size: 11px; padding-top: 1px; }
  .log-body { flex: 1; min-width: 0; }
  .log-subject { margin-bottom: 4px; font-weight: 600; font-size: 11px; }
  .log-subject.out { color: var(--green); }
  .log-subject.in { color: var(--blue); }
  .log-subject.err { color: var(--red); }
  .log-data { color: var(--text-muted); white-space: pre-wrap; word-break: break-all; line-height: 1.55; font-size: 11px; }
  .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; }
  .empty-icon { font-size: 28px; opacity: 0.3; }
  .empty-text { color: var(--text-muted); font-size: 13px; font-family: inherit; }
</style>
</head>
<body>

<header>
  <div class="header-left">
    <div class="header-logo">
      <svg viewBox="0 0 12 12"><path d="M2 2h3v3H2zm5 0h3v3H7zM2 7h3v3H2zm5 0h3v3H7z"/></svg>
    </div>
    <h1>ai-media-generation-service <span>/ dev</span></h1>
  </div>
  <span class="badge disconnected" id="wsStatus">disconnected</span>
</header>

<div class="main">
  <div class="sidebar">
    <div class="section">
      <div class="section-label">Identifiants</div>
      <div class="row">
        <div class="field"><label>projectId</label><input id="projectId" value="test-001"></div>
        <div class="field"><label>executionId</label><input id="executionId" value="exec-001"></div>
      </div>
    </div>

    <div class="section">
      <div class="section-label">Style visuel</div>
      <div class="field">
        <label>visualStyle</label>
        <input id="visualStyle" value="watercolor illustration, soft colors, storybook style">
      </div>
      <div class="field">
        <label>negativePrompt</label>
        <input id="negativePrompt" value="ugly, blurry, low quality">
      </div>
    </div>

    <div class="section">
      <div class="section-label">Personnages</div>
      <div id="characters"></div>
      <button class="btn-add" onclick="addCharacter()">+ Ajouter un personnage</button>
    </div>

    <div class="section">
      <div class="section-label">Lieux</div>
      <div id="locations"></div>
      <button class="btn-add" onclick="addLocation()">+ Ajouter un lieu</button>
    </div>

    <button class="btn-submit" id="submitBtn" onclick="send()">Publier l'event</button>
  </div>

  <div class="logs-panel">
    <div class="logs-header">
      <span>Logs NATS</span>
      <button class="btn-clear" onclick="clearLogs()">Vider</button>
    </div>
    <div id="logs">
      <div class="empty">
        <div class="empty-icon">◎</div>
        <div class="empty-text">En attente d'événements...</div>
      </div>
    </div>
  </div>
</div>

<script>
let charCount = 0, locCount = 0, logsEmpty = true;

function addCharacter(id='', desc='') {
  charCount++;
  const n = charCount;
  const div = document.createElement('div');
  div.className = 'card';
  div.innerHTML = `
    <div class="card-title">Personnage #${n}</div>
    <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
    <div class="field"><label>characterId</label><input class="char-id" value="${id || 'char-' + n}"></div>
    <div class="field"><label>physicalDescription</label><input class="char-desc" value="${desc}"></div>
  `;
  document.getElementById('characters').appendChild(div);
}

function addLocation(id='', desc='') {
  locCount++;
  const n = locCount;
  const div = document.createElement('div');
  div.className = 'card';
  div.innerHTML = `
    <div class="card-title">Lieu #${n}</div>
    <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
    <div class="field"><label>locationId</label><input class="loc-id" value="${id || 'loc-' + n}"></div>
    <div class="field"><label>description</label><input class="loc-desc" value="${desc}"></div>
  `;
  document.getElementById('locations').appendChild(div);
}

async function send() {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true; btn.textContent = 'Envoi en cours...';
  const payload = {
    projectId: document.getElementById('projectId').value,
    executionId: document.getElementById('executionId').value,
    bookStyle: {
      visualStyle: document.getElementById('visualStyle').value,
      negativePrompt: document.getElementById('negativePrompt').value,
    },
    characters: [...document.querySelectorAll('#characters .card')].map(el => ({
      characterId: el.querySelector('.char-id').value,
      physicalDescription: el.querySelector('.char-desc').value,
    })),
    locations: [...document.querySelectorAll('#locations .card')].map(el => ({
      locationId: el.querySelector('.loc-id').value,
      description: el.querySelector('.loc-desc').value,
    })),
  };
  try {
    await fetch('/dev/publish', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    appendLog('sent', 'out', 'visiobook.media.generate_references', payload);
  } catch (e) {
    appendLog('error', 'err', 'ERROR', { message: e.message });
  }
  btn.disabled = false; btn.textContent = 'Publier l\\'event';
}

function appendLog(type, subjectClass, subject, data) {
  const logs = document.getElementById('logs');
  if (logsEmpty) { logs.innerHTML = ''; logsEmpty = false; }
  const el = document.createElement('div');
  el.className = 'log-entry ' + type;
  const time = new Date().toLocaleTimeString('fr-FR', { hour12: false });
  el.innerHTML = `
    <span class="log-time">${time}</span>
    <div class="log-body">
      <div class="log-subject ${subjectClass}">${subject}</div>
      <div class="log-data">${JSON.stringify(data, null, 2)}</div>
    </div>`;
  logs.appendChild(el);
  logs.scrollTop = logs.scrollHeight;
}

function clearLogs() {
  document.getElementById('logs').innerHTML = '<div class="empty"><div class="empty-icon">◎</div><div class="empty-text">En attente d\\'événements...</div></div>';
  logsEmpty = true;
}

function connectWS() {
  const ws = new WebSocket('ws://' + location.host + '/dev/ws');
  const status = document.getElementById('wsStatus');
  ws.onopen = () => { status.className = 'badge connected'; status.textContent = 'connected'; };
  ws.onmessage = (e) => { const m = JSON.parse(e.data); appendLog('', 'in', m.subject, m.data); };
  ws.onclose = () => { status.className = 'badge disconnected'; status.textContent = 'disconnected'; setTimeout(connectWS, 3000); };
}

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
