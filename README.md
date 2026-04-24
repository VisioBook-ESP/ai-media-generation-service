# AI Media Generation Service

Service de generation de medias pour Visiobook. Orchestre des workflows ComfyUI (FLUX, Redux, LTX-Video 2.3) via NATS JetStream pour produire des illustrations et animations de livres animes.

## Architecture

```
NATS JetStream                    ComfyUI (RunPod GPU Pod)
     |                                    |
     v                                    v
 FastAPI Service  ---- HTTP/WS ---->  GPU Inference
     |                                    |
     v                                    v
 S3 / MinIO                        Generated Media
```

Le service ecoute un unique sujet NATS (`visiobook.media.generate`) et execute un pipeline sequentiel :

1. **References personnages** - Portraits plein pied via FLUX.1-dev (advanced sampler)
2. **References lieux** - Environnements via FLUX.1-dev
3. **Scenes** - Illustrations avec Redux (consistance visuelle personnage + lieu)
4. **Animations** - Image-to-video via LTX-Video 2.3 22B (two-pass + Gemma 3 prompt enhancement)

## Stack technique

| Composant | Technologie |
|---|---|
| API | FastAPI + Uvicorn |
| Messaging | NATS JetStream |
| Inference GPU | ComfyUI latest |
| Image generation | FLUX.1-dev (ModelSamplingFlux + SamplerCustomAdvanced) |
| Style consistency | FLUX Redux (StyleModelApply) |
| Animation | LTX-Video 2.3 22B fp8 (two-pass + Gemma 3 12B) |
| Storage | S3 / MinIO (prod) ou filesystem local (dev) |
| Infrastructure | Docker + RunPod / Kubernetes |

## Prerequis

- Python 3.12+
- NATS Server avec JetStream active
- ComfyUI latest avec le custom node `ComfyUI-LTXVideo`
- S3 / MinIO pour le stockage (production) ou stockage local (dev)
- GPU 24GB+ VRAM (RTX 4090, A100, L40S, ...)

## Installation

```bash
git clone <repo-url>
cd ai-media-generation-service

# Dependances (prod)
pip install -r requirements.txt
# ou : uv pip install -r requirements.txt

# Dependances dev (tests, lint, format)
pip install -r requirements-dev.txt

# Configurer l'environnement
cp .env.example .env
# Editer .env avec vos valeurs
```

## Configuration

Les variables sont lues depuis l'environnement ou un fichier `.env`. Les champs inconnus sont ignores (`extra="ignore"`).

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8087` | Port du service |
| `ENV` | `development` | `development` (stockage local) ou `production` (S3/MinIO) |
| `NATS_URL` | `nats://nats:4222` | URL du serveur NATS |
| `NATS_STREAM` | `visiobook` | Nom du stream JetStream |
| `COMFYUI_URL` | `http://localhost:8188` | URL de l'instance ComfyUI |
| `MINIO_ENDPOINT` | `localhost` | Hostname du serveur S3/MinIO |
| `MINIO_PORT` | `9000` | Port du serveur S3/MinIO |
| `MINIO_USE_SSL` | `false` | `true` pour HTTPS |
| `MINIO_ACCESS_KEY` | `minioadmin` | Access key |
| `MINIO_SECRET_KEY` | `minioadmin` | Secret key |
| `MINIO_BUCKET_RESULTS` | `analysis-results` | Nom du bucket |

L'URL S3 complete est construite automatiquement via la propriete `S3_ENDPOINT_URL` (`{scheme}://{MINIO_ENDPOINT}:{MINIO_PORT}`).

## Lancement

### Developpement

```bash
# Demarrer NATS + le service avec hot-reload + dev UI
./scripts/dev.sh
```

La dev UI est accessible sur `http://localhost:8087/dev/` — elle permet d'envoyer des messages NATS et de visualiser les evenements en temps reel.

### Production (Kubernetes)

En cluster, pointer `MINIO_ENDPOINT` vers le service MinIO :
```
MINIO_ENDPOINT=minio-analysis.visiobook-namespace.svc.cluster.local
MINIO_PORT=9000
```

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8087
```

## Format du message d'entree

Publier sur le sujet NATS `visiobook.media.generate` :

```json
{
  "projectId": "uuid",
  "executionId": "uuid",
  "userId": "uuid",
  "characters": [
    {
      "name": "Alice",
      "description": "protagoniste, jeune femme courageuse",
      "physicalDescription": "young woman, long auburn hair, green eyes, fair skin",
      "portraitPrompt": "young woman, long auburn hair reaching shoulders, bright green eyes, fair freckled skin, dark blue traveling cloak, full body character reference, standing pose, entire body visible, neutral background, front view, highly detailed",
      "portraitNegativePrompt": "multiple people, blurry, bad anatomy, extra limbs"
    }
  ],
  "locations": [
    {
      "locationId": "forest_clearing",
      "name": "La clairiere sombre",
      "descriptionPrompt": "ancient forest clearing, tall oak trees, moss-covered ground, golden sunlight through canopy, environment concept art, wide angle, no characters",
      "negativePrompt": "people, characters, text, modern objects",
      "sourceSceneOrders": [0, 2]
    }
  ],
  "scenes": [
    {
      "order": 0,
      "text": "Alice penetra dans la clairiere...",
      "description": "Arrivee dans la foret",
      "imagePrompt": "young woman with auburn hair in dark blue cloak entering a misty ancient forest clearing, golden sunlight filtering through tall oak trees, moss-covered ground, cinematic composition, storybook illustration",
      "negativePrompt": "duplicate character, extra limbs, bad anatomy",
      "duration": 5,
      "sentiment": "mysterious",
      "charactersPresent": ["Alice"],
      "locationId": "forest_clearing"
    }
  ],
  "correlationId": "uuid"
}
```

En dev, tu peux aussi POSTer ce payload sur `http://localhost:8087/dev/generate` — le service republie sur NATS pour toi.

### Champs cles

- `characters[].name` : identifiant du personnage, reference par `scenes[].charactersPresent`
- `characters[].portraitPrompt` : prompt FLUX pour generer le portrait de reference (plein pied)
- `locations[].locationId` : identifiant du lieu, reference par `scenes[].locationId`
- `locations[].descriptionPrompt` : prompt FLUX pour generer l'image de reference du lieu
- `scenes[].imagePrompt` : prompt FLUX pour generer l'illustration de la scene
- `scenes[].order` : ordre sequentiel des scenes (0, 1, 2, ...)
- `scenes[].charactersPresent` : liste de noms de personnages presents (le premier est utilise pour Redux)
- `scenes[].duration` : duree de l'animation en secondes (2-6s, defaut 4s)

## Modes de generation de scene

Le pipeline choisit automatiquement le workflow ComfyUI selon les references disponibles :

| Mode | Personnage ref | Lieu ref | Workflow |
|---|---|---|---|
| `text` | - | - | `flux_scene.json` |
| `location` | - | oui | `flux_scene_redux.json` (strength 0.5) |
| `character` | oui | - | `flux_scene_redux.json` (strength 0.35) |
| `character_location` | oui | oui | `flux_scene_dual_redux.json` (char 0.25 + loc 0.5) |

**Redux** (StyleModelApply) assure la consistance visuelle en transferant le style depuis les images de reference.

## Animation (LTX-Video 2.3)

Chaque scene illustree est animee via un workflow deux passes :

1. **Low-res** : generation initiale avec `euler_ancestral_cfg_pp` (10 steps)
2. **High-res** : latent upscale x2 + refinement avec `euler_cfg_pp` (7 steps)

Le prompt est enrichi automatiquement par **Gemma 3 12B** via `TextGenerateLTX2Prompt`. Parametres : 25 fps, duree configurable (2-6s).

## Evenements publies (NATS)

### Progression

```
visiobook.ai.progress
```
```json
{
  "executionId": "uuid",
  "step": "reference_generation | image_generation | animation_generation | pipeline",
  "progress": 0-100,
  "message": "..."
}
```

### Reference generee

```
visiobook.ai.reference.completed
```
```json
{
  "executionId": "uuid",
  "projectId": "uuid",
  "characterName": "Alice",
  "referenceImageUrl": "userId/projectId/characters/alice/reference.png"
}
```

### Scene generee

```
visiobook.ai.media.image.completed
```
```json
{
  "executionId": "uuid",
  "sceneOrder": 0,
  "mediaUrl": "userId/projectId/scenes/scene_0/image.png",
  "mode": "text | location | character | character_location"
}
```

### Animation generee

```
visiobook.ai.media.animation.completed
```
```json
{
  "executionId": "uuid",
  "sceneOrder": 0,
  "mediaUrl": "userId/projectId/animated_scenes/scene_0/animation.mp4"
}
```

### Pipeline termine

```
visiobook.ai.pipeline.completed
```
```json
{
  "executionId": "uuid",
  "projectId": "uuid"
}
```

### Erreur

```
visiobook.ai.media.failed | visiobook.ai.reference.failed
```
```json
{
  "executionId": "uuid",
  "sceneOrder": 0,
  "error": "message d'erreur"
}
```

## Structure de stockage

```
{userId}/
  {projectId}/
    characters/
      {character_name_slug}/
        reference.png
    locations/
      {locationId}/
        reference.png
    scenes/
      scene_{order}/
        image.png
    animated_scenes/
      scene_{order}/
        animation.mp4
```

## Health check

```
GET /health
```

```json
{
  "status": "ok",
  "checks": {
    "service": "ok",
    "nats": "ok",
    "comfyui": "ok"
  }
}
```

Le statut global est `ok` uniquement si tous les checks sont `ok`, sinon `degraded`. Valeurs possibles :
- `nats` : `ok` | `disconnected` | `error`
- `comfyui` : `ok` | `unavailable` (HTTP != 200) | `unreachable` (erreur reseau) | `not_configured`

## Tests

```bash
# Lancer la suite complete
pytest

# Avec coverage
pytest --cov=app --cov-report=term-missing

# Rapport HTML navigable
pytest --cov=app --cov-report=html
# puis ouvrir htmlcov/index.html
```

La suite contient ~150 tests unitaires avec fakes in-memory (aucun appel reseau). Coverage ~92%.

## Qualite du code

```bash
black app/ tests/     # format
ruff check app/ tests/  # lint
```

## Setup GPU (RunPod)

### 1. Telecharger les modeles

```bash
HF_TOKEN=hf_xxx bash scripts/setup_models.sh
```

Le script telecharge tous les modeles requis (~80 GB) sur le network volume `/runpod-volume/models/` :

| Modele | Taille | Dossier |
|---|---|---|
| FLUX.1-dev fp16 | ~23 GB | `diffusion_models/` |
| T5-XXL fp16 | ~9 GB | `text_encoders/` |
| CLIP-L | ~250 MB | `text_encoders/` |
| FLUX VAE | ~160 MB | `vae/` |
| FLUX Redux | ~300 MB | `style_models/` |
| SigCLIP Vision 384 | ~800 MB | `clip_vision/` |
| LTX-Video 2.3 22B fp8 | ~22 GB | `checkpoints/` |
| LTX-Video 2.3 distilled LoRA | ~500 MB | `loras/` |
| LTX-Video 2.3 spatial upscaler x2 | ~200 MB | `latent_upscale_models/` |
| Gemma 3 12B fp4 (text encoder LTX) | ~6 GB | `text_encoders/` |
| Gemma 3 abliterated LoRA | ~600 MB | `loras/` |

### 2. Build de l'image Docker ComfyUI

```bash
./scripts/build_docker.sh
```

Construit une image basee sur `worker-comfyui` avec ComfyUI latest, torchaudio, et `ComfyUI-LTXVideo`.

### 3. Deployer le pod

Le fichier `setup_pod.yaml` decrit la configuration du pod RunPod :

```yaml
image: vattv/visiobook-comfyui:v39
volume:
  mount_path: /runpod-volume
expose_ports:
  - 8188/http
gpu: 1x (24GB+ VRAM)
```

Les modeles sont lus depuis le volume via `extra_model_paths.yaml`.

## Structure du projet

```
app/
  api/
    health.py              # GET /health
    dev.py                 # Dev UI + POST /dev/generate + GET /dev/events
  clients/
    comfyui.py             # Client HTTP ComfyUI (retry + polling)
    s3_storage.py          # Client S3/MinIO (boto3)
    local_storage.py       # Stockage local (dev, filesystem)
  handlers/
    pipeline_handler.py    # Orchestrateur principal (monte dans main.py)
    reference_handler.py   # Handler isole references (non cable)
    scene_handler.py       # Handler isole scenes (non cable)
    animation_handler.py   # Handler isole animations (non cable)
  nats/
    consumer.py            # Consumer JetStream (visiobook.media.generate)
    publisher.py           # Publisher JetStream
  workflows/
    animation.py           # Builder workflow LTX-Video 2.3
    flux_portrait.py       # Builder workflow portrait
    flux_location.py       # Builder workflow lieu
    scene.py               # Builder workflow scene (4 variantes Redux)
    common.py              # Utilitaires (templates, seeds)
  config.py                # Configuration (pydantic-settings)
  main.py                  # Point d'entree FastAPI + lifespan
  storage_paths.py         # Construction des chemins de stockage
workflow_templates/        # Fichiers JSON ComfyUI (API format)
  flux_scene.json
  flux_scene_redux.json
  flux_scene_dual_redux.json
  flux_portrait.json
  flux_location.json
  ltxv_23_i2v.json
scripts/
  dev.sh                   # Lancement dev (NATS + hot-reload)
  start.sh                 # Lancement production
  test_prod.sh             # Smoke test de l'image prod
  setup_models.sh          # Telechargement modeles sur RunPod volume
  build_docker.sh          # Build image Docker ComfyUI
tests/                     # Suite pytest (~150 tests, coverage ~92%)
```

> Note : `reference_handler`, `scene_handler` et `animation_handler` sont des handlers par-phase testes isolement mais non cables dans `main.py`. Seul `pipeline_handler` est utilise en production. Ils servent de base pour une migration future vers un modele evenementiel decoupe.
