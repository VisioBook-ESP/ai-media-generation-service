# AI Media Generation Service

Service de generation de medias pour Visiobook. Orchestre des workflows ComfyUI (FLUX, PuLID, Redux, LTX-Video) via NATS JetStream pour produire des illustrations et animations de livres animes.

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

1. **References personnages** - Portraits via FLUX + prompts optimises
2. **References lieux** - Environnements via FLUX
3. **Scenes** - Illustrations avec PuLID (visage) + Redux (style/lieu)
4. **Animations** - Image-to-video via LTX-Video 13B

## Stack technique

| Composant | Technologie |
|---|---|
| API | FastAPI + Uvicorn |
| Messaging | NATS JetStream |
| Inference GPU | ComfyUI v0.18.5 |
| Image generation | FLUX.1-dev |
| Face consistency | PuLID-Flux v0.9.1 |
| Style transfer | FLUX Redux |
| Animation | LTX-Video 13B (0.9.8-dev) |
| Storage | S3 / MinIO |
| Infrastructure | Docker + RunPod / Kubernetes |

## Prerequis

- Python 3.12+
- NATS Server avec JetStream active
- ComfyUI avec les custom nodes : `ComfyUI-PuLID-Flux`, `ComfyUI-LTXVideo`
- S3 / MinIO pour le stockage
- GPU 24GB+ VRAM (RTX 4090, A100, L40S, ...)

## Installation

```bash
git clone <repo-url>
cd ai-media-generation-service

# Installer les dependances
uv sync  # ou pip install -r requirements.txt

# Configurer l'environnement
cp .env.example .env
# Editer .env avec vos valeurs
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8087` | Port du service |
| `ENV` | `development` | `development` (stockage local) ou `production` (S3) |
| `NATS_URL` | `nats://nats:4222` | URL du serveur NATS |
| `NATS_STREAM` | `visiobook` | Nom du stream JetStream |
| `COMFYUI_URL` | `http://localhost:8188` | URL de l'instance ComfyUI |
| `S3_ENDPOINT_URL` | `http://minio:9000` | Endpoint S3/MinIO |
| `S3_BUCKET` | `visiobook` | Nom du bucket |
| `S3_ACCESS_KEY` | `minioadmin` | Access key S3 |
| `S3_SECRET_KEY` | `minioadmin` | Secret key S3 |
| `S3_REGION` | `us-east-1` | Region S3 |

## Lancement

### Developpement

```bash
# Demarrer NATS + le service avec hot-reload
./scripts/dev.sh
```

### Production (Kubernetes)

Le service se deploie dans le meme cluster que MinIO. L'endpoint S3 est alors :
```
S3_ENDPOINT_URL=http://minio-analysis.visiobook-namespace.svc.cluster.local:9000
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

### Champs cles

- `characters[].portraitPrompt` : prompt optimise pour FLUX, utilise pour generer le portrait de reference
- `characters[].name` : identifiant du personnage, reference par `scenes[].charactersPresent`
- `locations[].descriptionPrompt` : prompt optimise pour FLUX, genere l'image de reference du lieu
- `locations[].locationId` : identifiant du lieu, reference par `scenes[].locationId`
- `scenes[].imagePrompt` : prompt optimise pour FLUX, genere l'illustration de la scene
- `scenes[].order` : ordre sequentiel des scenes (0, 1, 2, ...)
- `scenes[].charactersPresent` : liste de noms de personnages presents (le premier est utilise pour PuLID)

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
  "mediaUrl": "userId/projectId/animated_scenes/scene_0/animation.webp"
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

## Structure de stockage S3

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
        animation.webp
```

## Modes de generation de scene

Le pipeline choisit automatiquement le workflow ComfyUI selon les references disponibles :

| Mode | Personnage ref | Lieu ref | Workflow |
|---|---|---|---|
| `text` | - | - | `flux_scene.json` |
| `location` | - | oui | `flux_scene_redux.json` |
| `character` | oui | - | `flux_scene_pulid_redux.json` |
| `character_location` | oui | oui | `flux_scene_pulid_redux.json` |

- **PuLID** : transfert d'identite faciale depuis la reference personnage
- **Redux** : transfert de style visuel (personnage strength=0.25, lieu strength=0.5)

## Health check

```
GET /health
```

```json
{
  "status": "ok",
  "service": "ok",
  "nats": "connected",
  "comfyui": "ok"
}
```

## Setup GPU (RunPod)

### Telecharger les modeles

```bash
export HF_TOKEN=<votre token huggingface>
./scripts/setup_models.sh
```

Modeles requis (~80 GB) :
- FLUX.1-dev (fp16)
- T5-XXL + CLIP-L (encodeurs texte)
- FLUX VAE, Redux, PuLID v0.9.1, SigCLIP Vision
- EVA-CLIP + InsightFace (antelopev2)
- LTX-Video 13B

### Build de l'image Docker ComfyUI

```bash
./scripts/build_docker.sh
```

Construit une image basee sur `worker-comfyui` avec ComfyUI v0.18.5, PuLID-Flux, et LTX-Video.

## Structure du projet

```
app/
  api/
    health.py            # Health check endpoint
  clients/
    comfyui.py           # Client HTTP ComfyUI (avec retry)
    s3_storage.py        # Client S3/MinIO
    local_storage.py     # Stockage local (dev)
  handlers/
    pipeline_handler.py  # Orchestrateur principal du pipeline
  nats/
    consumer.py          # Consumer JetStream
    publisher.py         # Publisher JetStream
  workflows/
    animation.py         # Builder workflow LTX-Video
    flux_portrait.py     # Builder workflow portrait
    flux_location.py     # Builder workflow lieu
    scene.py             # Builder workflow scene (4 variantes)
    common.py            # Utilitaires (templates, seeds)
  config.py              # Configuration (pydantic-settings)
  main.py                # Point d'entree FastAPI
  storage_paths.py       # Construction des chemins S3
workflow_templates/      # Fichiers JSON ComfyUI (API format)
scripts/                 # Scripts de setup et deploiement
```
