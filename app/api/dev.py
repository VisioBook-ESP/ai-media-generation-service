import json
import logging

import nats
from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, Response

from app.clients.local_storage import _resolve

router = APIRouter()
logger = logging.getLogger(__name__)

_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Dev UI</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  :root {
    --bg: #0b0d14;
    --surface: #111420;
    --surface2: #181c2e;
    --surface3: #1e2338;
    --border: #252a40;
    --text: #e2e4f0;
    --text-muted: #5a607a;
    --text-soft: #8b91b0;
    --accent: #7b5cf5;
    --accent-hover: #6b4de0;
    --accent-light: rgba(123,92,245,0.15);
    --green: #22c55e;
    --green-bg: rgba(34,197,94,0.08);
    --red: #ef4444;
    --red-bg: rgba(239,68,68,0.08);
    --blue: #3b82f6;
    --blue-bg: rgba(59,130,246,0.08);
    --orange: #f97316;
    --orange-bg: rgba(249,115,22,0.08);
  }
  body {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: var(--bg); color: var(--text);
    height: 100vh; display: flex; flex-direction: column; overflow: hidden;
  }
  header {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 20px; height: 50px; border-bottom: 1px solid var(--border);
    background: var(--surface); flex-shrink: 0;
  }
  .header-left { display: flex; align-items: center; gap: 10px; }
  .header-logo {
    width: 24px; height: 24px; background: var(--accent); border-radius: 6px;
    display: flex; align-items: center; justify-content: center;
  }
  .header-logo svg { width: 13px; height: 13px; fill: white; }
  header h1 { font-size: 13px; font-weight: 600; color: var(--text); letter-spacing: -0.2px; }
  header h1 span { color: var(--text-muted); font-weight: 400; }
  .badge {
    display: inline-flex; align-items: center; gap: 5px;
    font-size: 11px; font-weight: 500; padding: 3px 9px; border-radius: 100px;
    border: 1px solid var(--border); color: var(--text-muted); background: var(--surface2);
  }
  .badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; background: var(--text-muted); }
  .badge.connected { border-color: rgba(34,197,94,0.3); color: var(--green); background: var(--green-bg); }
  .badge.connected::before { background: var(--green); }
  .badge.disconnected { border-color: rgba(239,68,68,0.3); color: var(--red); background: var(--red-bg); }
  .badge.disconnected::before { background: var(--red); }

  /* Tabs (top) */
  .top-tabs {
    display: flex; gap: 2px; padding: 10px 18px 0;
    border-bottom: 1px solid var(--border); background: var(--surface); flex-shrink: 0;
    position: relative; z-index: 10;
  }
  .top-tab {
    padding: 7px 13px; font-size: 12px; font-weight: 500; cursor: pointer;
    border-radius: 6px 6px 0 0; color: var(--text-muted);
    border: 1px solid transparent; border-bottom: none;
    background: none; transition: all 0.15s; font-family: inherit;
  }
  .top-tab:hover { color: var(--text); background: var(--surface2); }
  .top-tab.active {
    color: var(--accent); background: var(--surface);
    border-color: var(--border); border-bottom-color: var(--surface);
    font-weight: 600;
  }
  .tab-pill {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 16px; height: 16px; border-radius: 100px; font-size: 10px;
    font-weight: 700; margin-left: 5px; padding: 0 4px;
    background: var(--surface2); color: var(--text-muted);
  }
  .top-tab.active .tab-pill { background: var(--accent-light); color: var(--accent); }

  .main { display: grid; grid-template-columns: 380px 1fr; flex: 1; overflow: hidden; }

  /* Left sidebar */
  .sidebar {
    display: flex; flex-direction: column;
    border-right: 1px solid var(--border); background: var(--surface); overflow: hidden;
  }
  .tab-content { flex: 1; overflow-y: auto; }
  .tab-panel { display: none; }
  .tab-panel.active { display: block; }

  .section { padding: 14px 18px; border-bottom: 1px solid var(--border); }
  .section-label {
    font-size: 10px; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.8px; color: var(--text-muted); margin-bottom: 10px;
  }
  label { font-size: 11px; font-weight: 500; color: var(--text-soft); display: block; margin-bottom: 3px; }
  input, textarea, select {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); padding: 6px 9px; font-size: 12px; border-radius: 6px;
    transition: border-color 0.15s, box-shadow 0.15s; font-family: inherit;
  }
  textarea { resize: vertical; min-height: 56px; }
  input:focus, textarea:focus, select:focus {
    outline: none; border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-light);
  }
  .row { display: flex; gap: 8px; }
  .row > * { flex: 1; }
  .field { margin-bottom: 8px; }
  .field:last-child { margin-bottom: 0; }

  .card {
    background: var(--surface2); border: 1px solid var(--border);
    border-radius: 7px; padding: 11px 12px; margin-bottom: 7px; position: relative;
  }
  .card.scene-card { border-left: 2px solid var(--accent); }
  .card.char-ref-card { border-left: 2px solid var(--orange); background: var(--orange-bg); }
  .card.loc-ref-card { border-left: 2px solid var(--blue); background: var(--blue-bg); }
  .card-title {
    font-size: 10px; font-weight: 600; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 8px;
  }
  .btn-remove {
    position: absolute; top: 9px; right: 9px; background: none; border: none;
    color: var(--text-muted); cursor: pointer; font-size: 15px; line-height: 1;
    padding: 2px 5px; border-radius: 4px; transition: all 0.15s;
  }
  .btn-remove:hover { color: var(--red); background: var(--red-bg); }
  .btn-add {
    width: 100%; background: none; border: 1px dashed var(--border);
    color: var(--text-muted); padding: 7px; cursor: pointer;
    font-size: 11px; font-weight: 500; border-radius: 6px; transition: all 0.15s;
    font-family: inherit; margin-top: 3px;
  }
  .btn-add:hover { border-color: var(--accent); color: var(--accent); background: var(--accent-light); }

  .btn-submit {
    margin: 12px 18px; border: none; color: white;
    padding: 9px 18px; cursor: pointer; font-size: 12px; font-weight: 600;
    border-radius: 7px; width: calc(100% - 36px); transition: background 0.15s;
    font-family: inherit; letter-spacing: 0.1px; flex-shrink: 0;
  }
  .btn-submit.refs { background: var(--accent); }
  .btn-submit.refs:hover { background: var(--accent-hover); }
  .btn-submit.scenes { background: var(--orange); }
  .btn-submit.scenes:hover { background: #e06010; }
  .btn-submit:disabled { background: var(--surface2) !important; color: var(--text-muted); cursor: not-allowed; }

  /* Right panel */
  .right-panel { display: flex; flex-direction: column; overflow: hidden; background: var(--bg); }

  /* Right tabs */
  .right-tabs {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0 16px; height: 46px; border-bottom: 1px solid var(--border);
    background: var(--surface); flex-shrink: 0;
  }
  .right-tabs-nav { display: flex; gap: 4px; }
  .right-tab {
    padding: 5px 12px; font-size: 12px; font-weight: 500; cursor: pointer;
    border-radius: 6px; color: var(--text-muted); border: 1px solid transparent;
    background: none; transition: all 0.15s; font-family: inherit;
  }
  .right-tab:hover { color: var(--text); background: var(--surface2); }
  .right-tab.active { color: var(--text); background: var(--surface2); border-color: var(--border); font-weight: 600; }
  .btn-clear {
    background: none; border: 1px solid var(--border); color: var(--text-muted);
    padding: 4px 10px; cursor: pointer; font-size: 11px; font-weight: 500;
    border-radius: 5px; transition: all 0.15s; font-family: inherit;
  }
  .btn-clear:hover { border-color: var(--text-soft); color: var(--text); }

  .right-content { flex: 1; overflow: hidden; position: relative; }
  .right-pane { display: none; width: 100%; height: 100%; overflow-y: auto; }
  .right-pane.active { display: block; }

  /* Images panel */
  .images-grid {
    display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px; padding: 16px;
  }
  .image-card {
    background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
    overflow: hidden; cursor: pointer; transition: all 0.2s;
  }
  .image-card:hover { border-color: var(--accent); transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0,0,0,0.4); }
  .image-card img { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block; }
  .image-card-meta {
    padding: 8px 10px; border-top: 1px solid var(--border);
  }
  .image-card-id { font-size: 11px; font-weight: 600; color: var(--text); margin-bottom: 2px; }
  .image-card-type {
    font-size: 10px; font-weight: 500; padding: 1px 6px; border-radius: 100px;
    display: inline-block;
  }
  .image-card-type.scene { background: var(--accent-light); color: var(--accent); }
  .image-card-type.character { background: var(--orange-bg); color: var(--orange); }
  .image-card-type.location { background: var(--blue-bg); color: var(--blue); }
  .images-empty {
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    height: 100%; gap: 10px; color: var(--text-muted);
  }
  .images-empty-icon { font-size: 36px; opacity: 0.2; }
  .images-empty-text { font-size: 13px; }

  /* Lightbox */
  .lightbox {
    display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.92);
    z-index: 1000; align-items: center; justify-content: center;
  }
  .lightbox.open { display: flex; }
  .lightbox img { max-width: 90vw; max-height: 90vh; border-radius: 8px; object-fit: contain; }
  .lightbox-close {
    position: fixed; top: 16px; right: 20px; background: none; border: none;
    color: white; font-size: 28px; cursor: pointer; opacity: 0.7; line-height: 1;
  }
  .lightbox-close:hover { opacity: 1; }

  /* Logs */
  #logs { padding: 10px 14px; font-family: 'JetBrains Mono', 'SF Mono', monospace; }
  .log-entry {
    display: flex; gap: 10px; padding: 8px 10px; border-radius: 6px;
    margin-bottom: 3px; font-size: 11px; align-items: flex-start;
    border: 1px solid transparent; transition: background 0.1s;
  }
  .log-entry:hover { background: var(--surface); }
  .log-entry.sent { border-color: rgba(34,197,94,0.2); background: var(--green-bg); }
  .log-entry.error { border-color: rgba(239,68,68,0.2); background: var(--red-bg); }
  .log-time { color: var(--text-muted); white-space: nowrap; font-size: 10px; padding-top: 1px; }
  .log-body { flex: 1; min-width: 0; }
  .log-subject { margin-bottom: 3px; font-weight: 600; font-size: 10px; }
  .log-subject.out { color: var(--green); }
  .log-subject.in { color: var(--blue); }
  .log-subject.err { color: var(--red); }
  .log-data { color: var(--text-soft); white-space: pre-wrap; word-break: break-all; line-height: 1.5; font-size: 10px; }
  .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; gap: 8px; }
  .empty-icon { font-size: 28px; opacity: 0.2; }
  .empty-text { color: var(--text-muted); font-size: 12px; font-family: inherit; }

  .nested-section { margin-top: 9px; padding-top: 9px; border-top: 1px solid var(--border); }
  .nested-label { font-size: 10px; font-weight: 600; color: var(--orange); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 7px; }
  .ref-toggle { display: flex; gap: 5px; margin-bottom: 7px; }
  .ref-toggle-btn {
    flex: 1; padding: 5px 7px; font-size: 11px; font-weight: 500; cursor: pointer;
    border: 1px solid var(--border); border-radius: 5px; background: var(--surface2);
    color: var(--text-muted); font-family: inherit; transition: all 0.15s;
  }
  .ref-toggle-btn.active-char { border-color: rgba(249,115,22,0.4); color: var(--orange); background: var(--orange-bg); }
  .ref-toggle-btn.active-loc { border-color: rgba(59,130,246,0.4); color: var(--blue); background: var(--blue-bg); }
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

<div class="top-tabs">
  <button class="top-tab active" onclick="switchTab('refs')" id="tab-refs">
    Références <span class="tab-pill">1</span>
  </button>
  <button class="top-tab" onclick="switchTab('scenes')" id="tab-scenes">
    Scènes <span class="tab-pill">2</span>
  </button>
  <button class="top-tab" onclick="switchTab('animations')" id="tab-animations">
    Animations <span class="tab-pill">3</span>
  </button>
</div>

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
        <input id="visualStyle" value="cinematic watercolor illustration, rich dramatic lighting, highly detailed, painterly textures, storybook aesthetic, warm golden tones">
      </div>
      <div class="field">
        <label>negativePrompt</label>
        <input id="negativePrompt" value="ugly, blurry, low quality, deformed, extra limbs, bad anatomy, watermark, text, oversaturated">
      </div>
    </div>

    <div class="tab-content">
      <div class="tab-panel active" id="panel-refs">
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
      </div>

      <div class="tab-panel" id="panel-scenes">
        <div class="section">
          <div class="section-label">Scènes</div>
          <div id="scenes"></div>
          <button class="btn-add" onclick="addScene()">+ Ajouter une scène</button>
        </div>
      </div>

      <div class="tab-panel" id="panel-animations">
        <div class="section">
          <div class="section-label">Scènes à animer</div>
          <div id="animScenes"></div>
          <button class="btn-add" onclick="addAnimScene()">+ Ajouter une scène</button>
        </div>
      </div>
    </div>

    <button class="btn-submit refs" id="submitBtn" onclick="send()">
      Publier generate_references
    </button>
  </div>

  <div class="right-panel">
    <div class="right-tabs">
      <div class="right-tabs-nav">
        <button class="right-tab active" onclick="switchRight('images')" id="rtab-images">
          Images <span class="tab-pill" id="img-count">0</span>
        </button>
        <button class="right-tab" onclick="switchRight('logs')" id="rtab-logs">Logs</button>
      </div>
      <button class="btn-clear" onclick="clearRight()">Vider</button>
    </div>
    <div class="right-content">
      <div class="right-pane active" id="rpane-images">
        <div class="images-grid" id="imagesGrid"></div>
        <div class="images-empty" id="imagesEmpty">
          <div class="images-empty-icon">🖼</div>
          <div class="images-empty-text">Les images générées apparaîtront ici</div>
        </div>
      </div>
      <div class="right-pane" id="rpane-logs">
        <div id="logs">
          <div class="empty">
            <div class="empty-icon">◎</div>
            <div class="empty-text">En attente d'événements...</div>
          </div>
        </div>
      </div>
    </div>
  </div>
</div>

<div class="lightbox" id="lightbox" onclick="closeLightbox(event)">
  <button class="lightbox-close" onclick="closeLightbox()">×</button>
  <img id="lightboxImg" src="" alt="">
</div>

<script>
let charCount = 0, locCount = 0, sceneCount = 0, logsEmpty = true, imgCount = 0;
let activeTab = 'refs', activeRight = 'images';

function switchTab(tab) {
  activeTab = tab;
  document.querySelectorAll('.top-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('tab-' + tab).classList.add('active');
  document.getElementById('panel-' + tab).classList.add('active');
  const btn = document.getElementById('submitBtn');
  if (tab === 'refs') {
    btn.textContent = 'Publier generate_references';
    btn.className = 'btn-submit refs';
  } else if (tab === 'scenes') {
    btn.textContent = 'Publier image_generation';
    btn.className = 'btn-submit scenes';
  } else {
    btn.textContent = 'Publier animation_generation';
    btn.className = 'btn-submit scenes';
  }
}

function switchRight(pane) {
  activeRight = pane;
  document.querySelectorAll('.right-tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.right-pane').forEach(p => p.classList.remove('active'));
  document.getElementById('rtab-' + pane).classList.add('active');
  document.getElementById('rpane-' + pane).classList.add('active');
}

function clearRight() {
  if (activeRight === 'images') {
    document.getElementById('imagesGrid').innerHTML = '';
    imgCount = 0;
    document.getElementById('img-count').textContent = '0';
    document.getElementById('imagesEmpty').style.display = '';
  } else {
    document.getElementById('logs').innerHTML = '<div class="empty"><div class="empty-icon">◎</div><div class="empty-text">En attente d\\'événements...</div></div>';
    logsEmpty = true;
  }
}

function addCharacter(id='', desc='') {
  charCount++;
  const n = charCount;
  const div = document.createElement('div');
  div.className = 'card';
  div.innerHTML = `
    <div class="card-title">Personnage #${n}</div>
    <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
    <div class="field"><label>characterId</label><input class="char-id" value="${id || 'char-' + n}"></div>
    <div class="field"><label>physicalDescription</label><input class="char-desc" value="${desc}" placeholder="Describe the full body, outfit, silhouette, accessories..."></div>
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

function addScene(id='', imagePrompt='') {
  sceneCount++;
  const n = sceneCount;
  const div = document.createElement('div');
  div.className = 'card scene-card';
  div.innerHTML = `
    <div class="card-title">Scène #${n}</div>
    <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
    <div class="field"><label>sceneId</label><input class="scene-id" value="${id || 'scene-' + n}"></div>
    <div class="field"><label>prompt image</label><textarea class="scene-img-prompt" rows="2">${imagePrompt}</textarea></div>
    <div class="nested-section">
      <div class="nested-label">Référence visuelle (optionnel)</div>
      <div class="ref-toggle">
        <button class="ref-toggle-btn" onclick="setRef(this, 'char')">+ Personnage</button>
        <button class="ref-toggle-btn" onclick="setRef(this, 'loc')">+ Lieu</button>
      </div>
      <div class="scene-ref"></div>
    </div>
  `;
  document.getElementById('scenes').appendChild(div);
}

function setRef(btn, type) {
  const nested = btn.closest('.nested-section');
  const container = nested.querySelector('.scene-ref');
  const activeClass = 'active-' + type;
  const cardClass = type === 'char' ? 'char-ref-card' : 'loc-ref-card';

  // Toggle off: remove card and deactivate button
  if (btn.classList.contains(activeClass)) {
    btn.className = 'ref-toggle-btn';
    const existing = container.querySelector('.' + cardClass);
    if (existing) existing.remove();
    return;
  }

  // Toggle on: activate button and inject card if not already there
  btn.className = 'ref-toggle-btn ' + activeClass;
  if (!container.querySelector('.' + cardClass)) {
    const card = document.createElement('div');
    card.className = 'card ' + cardClass;
    card.style.marginTop = '5px';
    if (type === 'char') {
      card.innerHTML = `
        <div class="field"><label>characterId</label><input class="ref-char-id" value="char-1"></div>
        <div class="field"><label>referenceImageUrl</label><input class="ref-img-url" value="projects/test-001/characters/char-1/reference.png"></div>`;
    } else {
      card.innerHTML = `
        <div class="field"><label>locationId</label><input class="ref-loc-id" value="loc-1"></div>
        <div class="field"><label>referenceImageUrl</label><input class="ref-img-url" value="projects/test-001/locations/loc-1/reference.png"></div>`;
    }
    container.appendChild(card);
  }
}

let animSceneCount = 0;
function addAnimScene(id='', prompt='', imageUrl='') {
  animSceneCount++;
  const n = animSceneCount;
  const div = document.createElement('div');
  div.className = 'card scene-card';
  div.innerHTML = `
    <div class="card-title">Scène #${n}</div>
    <button class="btn-remove" onclick="this.parentElement.remove()">×</button>
    <div class="field"><label>sceneId</label><input class="anim-scene-id" value="${id || 'scene-' + n}"></div>
    <div class="field"><label>prompt (motion description)</label><textarea class="anim-prompt" rows="2">${prompt}</textarea></div>
    <div class="field"><label>sceneImageUrl (storage path)</label><input class="anim-img-url" value="${imageUrl || 'projects/test-001/scenes/scene-' + n + '/image.png'}"></div>
  `;
  document.getElementById('animScenes').appendChild(div);
}

async function send() {
  const btn = document.getElementById('submitBtn');
  btn.disabled = true;
  const origText = btn.textContent;
  btn.textContent = 'Envoi...';
  let subject, payload;
  if (activeTab === 'refs') {
    subject = 'visiobook.media.generate_references';
    payload = {
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
  } else if (activeTab === 'scenes') {
    subject = 'visiobook.workflow.step.image_generation';
    payload = {
      projectId: document.getElementById('projectId').value,
      executionId: document.getElementById('executionId').value,
      bookStyle: {
        visualStyle: document.getElementById('visualStyle').value,
        negativePrompt: document.getElementById('negativePrompt').value,
      },
      scenes: [...document.querySelectorAll('#scenes .scene-card')].map(el => {
        const charCard = el.querySelector('.char-ref-card');
        const locCard = el.querySelector('.loc-ref-card');
        const scene = {
          sceneId: el.querySelector('.scene-id').value,
          prompt: {
            image: el.querySelector('.scene-img-prompt').value,
          }
        };
        if (charCard) {
          scene.characterRef = {
            characterId: charCard.querySelector('.ref-char-id').value,
            referenceImageUrl: charCard.querySelector('.ref-img-url').value,
          };
        }
        if (locCard) {
          scene.locationRef = {
            locationId: locCard.querySelector('.ref-loc-id').value,
            referenceImageUrl: locCard.querySelector('.ref-img-url').value,
          };
        }
        return scene;
      }),
    };
  } else {
    subject = 'visiobook.workflow.step.animation_generation';
    payload = {
      projectId: document.getElementById('projectId').value,
      executionId: document.getElementById('executionId').value,
      scenes: [...document.querySelectorAll('#animScenes .scene-card')].map(el => ({
        sceneId: el.querySelector('.anim-scene-id').value,
        prompt: { image: el.querySelector('.anim-prompt').value },
        sceneImageUrl: el.querySelector('.anim-img-url').value,
      })),
    };
  }
  try {
    await fetch('/dev/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ subject, payload }),
    });
    appendLog('sent', 'out', subject, payload);
  } catch (e) {
    appendLog('error', 'err', 'ERROR', { message: e.message });
  }
  btn.disabled = false;
  btn.textContent = origText;
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

function addImage(mediaUrl, entityId, type) {
  const grid = document.getElementById('imagesGrid');
  document.getElementById('imagesEmpty').style.display = 'none';
  imgCount++;
  document.getElementById('img-count').textContent = imgCount;
  const src = '/dev/files/' + mediaUrl;
  const card = document.createElement('div');
  card.className = 'image-card';
  card.onclick = () => openLightbox(src);
  card.innerHTML = `
    <img src="${src}" alt="${entityId}" loading="lazy">
    <div class="image-card-meta">
      <div class="image-card-id">${entityId}</div>
      <span class="image-card-type ${type}">${type}</span>
    </div>`;
  grid.prepend(card);
  if (activeRight !== 'images') switchRight('images');
}

function openLightbox(src) {
  document.getElementById('lightboxImg').src = src;
  document.getElementById('lightbox').classList.add('open');
}
function closeLightbox(e) {
  if (!e || e.target !== document.getElementById('lightboxImg')) {
    document.getElementById('lightbox').classList.remove('open');
  }
}
document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });

function connectWS() {
  const ws = new WebSocket('ws://' + location.host + '/dev/ws');
  const status = document.getElementById('wsStatus');
  ws.onopen = () => { status.className = 'badge connected'; status.textContent = 'connected'; };
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    appendLog('', 'in', m.subject, m.data);
    const d = m.data;
    if (m.subject === 'visiobook.ai.media.image.completed' && d.mediaUrl) {
      addImage(d.mediaUrl, d.sceneId || d.entityId || 'scene', 'scene');
    } else if (m.subject === 'visiobook.ai.reference.completed' && d.referenceImageUrl) {
      const type = d.characterId ? 'character' : 'location';
      const id = d.characterId || d.locationId || 'ref';
      addImage(d.referenceImageUrl, id, type);
    } else if (m.subject === 'visiobook.ai.media.animation.completed' && d.mediaUrl) {
      addImage(d.mediaUrl, d.sceneId || 'anim', 'scene');
    }
  };
  ws.onclose = () => {
    status.className = 'badge disconnected'; status.textContent = 'disconnected';
    setTimeout(connectWS, 3000);
  };
}

// Defaults
addCharacter('char-1', 'Lucas, 8 years old, messy dark brown hair, bright amber eyes full of curiosity, wearing an oversized navy explorer jacket with gold buttons and a worn leather satchel on his shoulder');
addLocation('loc-1', 'The Ancient Library — towering bookshelves reaching infinite heights, golden dust particles floating in warm light beams, hidden spiral staircases, leather-bound tomes glowing faintly');
addScene(
  'scene-1',
  'Lucas stands on a floating platform in the heart of the Ancient Library, ancient books swirling around him in a slow magical vortex, his amber eyes wide with awe, dramatic golden light rays pierce through the darkness above'
);
addAnimScene(
  'scene-1',
  'Golden dust particles floating upward, books gently hovering and rotating around the character, warm light rays shifting slowly, hair and clothes swaying softly',
  'projects/test-001/scenes/scene-1/image.png'
);
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
    subject = body.get("subject", "visiobook.media.generate_references")
    payload = body.get("payload", body)
    publisher = request.app.state.publisher
    await publisher.publish(subject, payload)
    return {"status": "ok"}


@router.get("/dev/files/{path:path}")
async def dev_files(path: str):
    file_path = _resolve(path)
    if not file_path.exists():
        return Response(status_code=404)
    return FileResponse(file_path)


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
        try:
            await nc.drain()
        except Exception:
            pass
