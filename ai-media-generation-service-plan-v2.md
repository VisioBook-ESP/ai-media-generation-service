# ai-media-generation-service — Plan technique complet (v2)

---

## 1. Rôle du service

Worker stateless en FastAPI qui transforme des événements NATS en jobs GPU RunPod Serverless. Il reçoit des prompts prêts à l'emploi et des URLs d'images de référence, construit les workflows JSON ComfyUI, envoie à RunPod, reçoit les résultats par webhook, upload vers MinIO, et publie les résultats sur NATS.

**Ce qu'il fait :**
- Génère les images de référence des personnages (portraits)
- Génère les images de référence des lieux récurrents
- Génère les images de chaque scène (avec injection IP-Adapter pour cohérence)
- Génère les vidéos animées à partir des images
- Génère la musique de fond et le sound design
- Assemble vidéo + audio en fichier final (ffmpeg)

**Ce qu'il ne fait PAS :**
- Analyser le texte (c'est l'ai-analysis-service)
- Matcher les personnages / détecter les doublons (c'est le core-project-service)
- Stocker l'état des projets, personnages, scènes (c'est le core-project-service)
- Gérer les fichiers directement (c'est le storage-service / MinIO)

**Principe : zero intelligence, 100% plomberie.** Toute la logique métier (matching personnages, enrichissement de prompts, style du livre) est gérée en amont. Ce service reçoit tout ce qu'il faut dans l'event NATS et exécute mécaniquement.

---

## 2. Stack technique

| Composant | Technologie |
|-----------|-------------|
| Framework | FastAPI (Python 3.12) |
| Serveur ASGI | uvicorn |
| Messagerie | NATS JetStream (nats-py) |
| HTTP client | httpx (async) |
| Validation | Pydantic v2 |
| Config | pydantic-settings (.env) |
| Assemblage vidéo | ffmpeg (subprocess) |
| Container | Docker |
| GPU Compute | RunPod Serverless |
| Génération média | ComfyUI (headless, API mode) |
| Port | 8087 |

---

## 3. Structure du projet

```
ai-media-generation-service/
├── app/
│   ├── __init__.py
│   ├── main.py                         # FastAPI app, lifespan, NATS connect
│   ├── config.py                       # Settings (env vars)
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── webhooks.py                 # POST /webhook/runpod
│   │   └── health.py                   # GET /health
│   │
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── storage.py                  # HTTP → storage-service (upload URLs)
│   │   └── runpod.py                   # HTTP → api.runpod.ai
│   │
│   ├── nats/
│   │   ├── __init__.py
│   │   ├── consumer.py                 # Subscribers NATS JetStream
│   │   └── publisher.py                # Publisher NATS
│   │
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── reference_handler.py        # Gère generate_references
│   │   ├── scene_handler.py            # Gère image_generation (scènes)
│   │   ├── audio_handler.py            # Gère audio_generation
│   │   └── webhook_handler.py          # Traite les callbacks RunPod
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── flux_portrait.py            # Workflow portrait personnage (référence)
│   │   ├── flux_scene.py               # Workflow scène sans personnage
│   │   ├── flux_scene_ipadapter.py     # Workflow scène avec IP-Adapter (cohérence)
│   │   ├── flux_location.py            # Workflow lieu de référence
│   │   ├── wan_video.py                # Workflow Wan 2.1 I2V
│   │   ├── ace_step_music.py           # Workflow ACE-Step musique
│   │   └── stable_audio_sfx.py         # Workflow Stable Audio SFX
│   │
│   ├── assembler/
│   │   ├── __init__.py
│   │   └── ffmpeg.py                   # Assemblage vidéo + audio via ffmpeg
│   │
│   └── models/
│       ├── __init__.py
│       └── schemas.py                  # Pydantic models (events, payloads)
│
├── workflow_templates/                  # JSON templates ComfyUI de base
│   ├── flux_portrait.json
│   ├── flux_scene.json
│   ├── flux_scene_ipadapter.json
│   ├── flux_location.json
│   ├── wan21_i2v.json
│   ├── ace_step.json
│   └── stable_audio.json
│
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. Configuration

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Service
    PORT: int = 8087
    ENV: str = "development"
    LOG_LEVEL: str = "info"

    # NATS
    NATS_URL: str = "nats://nats:4222"
    NATS_STREAM: str = "visiobook"

    # Storage Service
    STORAGE_URL: str = "http://storage-service:8085"

    # RunPod Serverless
    RUNPOD_API_KEY: str
    RUNPOD_ENDPOINT_IMAGE: str      # Flux.2 + IP-Adapter
    RUNPOD_ENDPOINT_VIDEO: str      # Wan 2.1 I2V
    RUNPOD_ENDPOINT_AUDIO: str      # ACE-Step + Stable Audio

    # Webhook
    WEBHOOK_BASE_URL: str           # URL publique du service
    WEBHOOK_SECRET: str = ""        # Secret pour valider les webhooks RunPod

    # Defaults
    DEFAULT_IMAGE_WIDTH: int = 1024
    DEFAULT_IMAGE_HEIGHT: int = 1024
    DEFAULT_VIDEO_WIDTH: int = 832
    DEFAULT_VIDEO_HEIGHT: int = 480
    DEFAULT_VIDEO_LENGTH: int = 81      # ~5 sec à 16 fps
    DEFAULT_VIDEO_FPS: int = 16

    class Config:
        env_file = ".env"
```

---

## 5. Les 3 événements NATS consommés

Le service écoute exactement 3 sujets NATS. Chaque event contient TOUT ce dont le service a besoin — aucun appel REST supplémentaire.

### 5.1 `visiobook.media.generate_references`

Déclenché par le core-project-service quand de nouveaux personnages ou lieux sont détectés et ont besoin d'une image de référence.

```json
{
  "projectId": "abc-123",
  "executionId": "exec-456",
  "bookStyle": {
    "visualStyle": "watercolor illustration, Saint-Exupéry style, soft muted colors",
    "negativePrompt": "photograph, 3d render, anime, modern"
  },
  "characters": [
    {
      "characterId": "char-001",
      "name": "Le narrateur",
      "physicalDescription": "petit garçon de 6 ans, cheveux châtains en désordre, yeux noisette, taches de rousseur, pull bleu marine"
    }
  ],
  "locations": [
    {
      "locationId": "loc-001",
      "name": "La chambre d'enfant",
      "description": "petite chambre aux murs beiges, plancher en bois, fenêtre avec rideaux, étagère de livres"
    }
  ]
}
```

**Ce que fait le handler :**
1. Pour chaque personnage → construit un workflow Flux.2 portrait (face caméra, fond neutre, style du livre)
2. Pour chaque lieu → construit un workflow Flux.2 paysage (vue d'ensemble, style du livre)
3. Envoie chaque job à RunPod endpoint image
4. Les webhooks de retour uploadent les images et publient `visiobook.ai.reference.completed` pour chaque image

### 5.2 `visiobook.workflow.step.image_generation`

Déclenché par le core-project-service quand toutes les références sont prêtes et qu'on peut générer les scènes.

```json
{
  "projectId": "abc-123",
  "versionId": "v1",
  "executionId": "exec-789",
  "bookStyle": {
    "visualStyle": "watercolor illustration, Saint-Exupéry style, soft muted colors",
    "negativePrompt": "photograph, 3d render, anime, modern",
    "musicGenre": "gentle piano, orchestral, nostalgic"
  },
  "characters": [
    {
      "characterId": "char-001",
      "name": "Le narrateur",
      "aliases": ["le petit garçon", "l'enfant"],
      "referenceImageUrl": "https://minio.internal/projects/abc/characters/char-001/reference.png"
    },
    {
      "characterId": "char-002",
      "name": "Les grandes personnes",
      "aliases": ["les adultes"],
      "referenceImageUrl": "https://minio.internal/projects/abc/characters/char-002/reference.png"
    }
  ],
  "locations": [
    {
      "locationId": "loc-001",
      "name": "La chambre d'enfant",
      "referenceImageUrl": "https://minio.internal/projects/abc/locations/loc-001/reference.png"
    }
  ],
  "scenes": [
    {
      "sceneId": "scene-001",
      "prompts": {
        "image": "a small boy sitting alone on a wooden floor reading a large illustrated book about the jungle, warm golden light from a window",
        "imageNegative": "ugly, blurry, deformed",
        "video": "the boy slowly turns the pages, his eyes widening with wonder, gentle camera push in",
        "musicTags": "gentle piano, childhood wonder, slow tempo, innocent",
        "sfx": "quiet room ambiance, pages turning softly, distant birds outside window"
      },
      "charactersPresent": ["Le narrateur"],
      "location": "La chambre d'enfant",
      "duration": 30
    },
    {
      "sceneId": "scene-002",
      "prompts": {
        "image": "a small boy holding up a drawing to tall stern-looking adults in a living room, the adults look confused, the boy looks hopeful",
        "imageNegative": "ugly, blurry, deformed",
        "video": "adults shake their heads disapprovingly, the boy's expression falls with disappointment, slow zoom on his face",
        "musicTags": "melancholic piano, strings, disillusion, slow",
        "sfx": "murmuring adult voices, paper rustling, quiet room"
      },
      "charactersPresent": ["Le narrateur", "Les grandes personnes"],
      "location": null,
      "duration": 25
    }
  ]
}
```

**Ce que fait le handler :**
1. Pour chaque scène :
   a. Détermine quels personnages sont présents → récupère leurs `referenceImageUrl`
   b. Détermine si un lieu de référence existe → récupère son `referenceImageUrl`
   c. Construit le prompt final : `bookStyle.visualStyle + ", " + scene.prompts.image`
   d. Choisit le workflow :
      - Si personnage(s) présent(s) → `flux_scene_ipadapter.json` avec IP-Adapter FaceID
      - Sinon → `flux_scene.json` simple
   e. Envoie à RunPod
2. Les webhooks de retour enchaînent automatiquement image → vidéo

### 5.3 `visiobook.workflow.step.audio_generation`

Déclenché par le core-project-service quand l'étape image_generation est terminée.

```json
{
  "projectId": "abc-123",
  "versionId": "v1",
  "executionId": "exec-789",
  "bookStyle": {
    "musicGenre": "gentle piano, orchestral, nostalgic"
  },
  "scenes": [
    {
      "sceneId": "scene-001",
      "prompts": {
        "musicTags": "gentle piano, childhood wonder, slow tempo",
        "sfx": "quiet room ambiance, pages turning, distant birds"
      },
      "duration": 30
    }
  ]
}
```

**Ce que fait le handler :**
1. Pour chaque scène, lance en parallèle :
   a. ACE-Step → musique (`bookStyle.musicGenre + ", " + scene.prompts.musicTags`)
   b. Stable Audio → SFX (`scene.prompts.sfx`)
2. Les webhooks de retour uploadent et publient les résultats

---

## 6. Les 6 événements NATS publiés

| Event | Payload | Quand |
|-------|---------|-------|
| `visiobook.ai.reference.completed` | `{ projectId, characterId?, locationId?, referenceImageUrl }` | Image de référence personnage/lieu générée |
| `visiobook.ai.reference.failed` | `{ projectId, characterId?, locationId?, error }` | Échec génération référence |
| `visiobook.ai.media.image.completed` | `{ executionId, sceneId, mediaUrl }` | Image de scène générée |
| `visiobook.ai.media.video.completed` | `{ executionId, sceneId, mediaUrl }` | Vidéo de scène générée |
| `visiobook.ai.media.audio.completed` | `{ executionId, sceneId, type: "music"\|"sfx", mediaUrl }` | Piste audio générée |
| `visiobook.ai.media.scene.completed` | `{ executionId, sceneId, finalVideoUrl, imageUrl, videoUrl, musicUrl, sfxUrl }` | Scène entièrement terminée (assemblage fait) |
| `visiobook.ai.media.failed` | `{ executionId, sceneId?, step, error, retryCount }` | Échec d'une étape |
| `visiobook.ai.progress` | `{ executionId, step, progress: 0-100, message? }` | Mise à jour progression |

---

## 7. Webhook RunPod et enchaînement des séquences

Le webhook est le point central qui orchestre l'enchaînement des 5 séquences pour chaque scène. Chaque job RunPod contient un `metadata` qui identifie le type de job et la scène concernée.

```python
# app/handlers/webhook_handler.py
from app.assembler.ffmpeg import assemble_scene

class WebhookHandler:
    def __init__(self, runpod, storage, publisher, settings):
        self.runpod = runpod
        self.storage = storage
        self.publisher = publisher
        self.settings = settings
        # Tracking en mémoire des résultats par scène (pour l'assemblage)
        # En production, utiliser Redis si multi-instance
        self._scene_results: dict[str, dict] = {}

    async def handle(self, body: dict):
        status = body["status"]
        metadata = body.get("input", {}).get("metadata", {})
        job_type = metadata["job_type"]
        job_id = body["id"]

        if status == "COMPLETED":
            output = body["output"]

            if job_type == "character_reference":
                await self._handle_character_reference(metadata, output)

            elif job_type == "location_reference":
                await self._handle_location_reference(metadata, output)

            elif job_type == "scene_image":
                await self._handle_scene_image(metadata, output)

            elif job_type == "scene_video":
                await self._handle_scene_video(metadata, output)

            elif job_type == "scene_music":
                await self._handle_scene_music(metadata, output)

            elif job_type == "scene_sfx":
                await self._handle_scene_sfx(metadata, output)

        elif status == "FAILED":
            await self._handle_failure(metadata, body.get("error"))

    # ── Référence personnage ──────────────────────────────────

    async def _handle_character_reference(self, metadata, output):
        """Portrait de référence généré → upload + publie"""
        character_id = metadata["character_id"]
        project_id = metadata["project_id"]

        image_url = await self._upload_image(
            output, f"projects/{project_id}/characters/{character_id}/reference.png"
        )

        await self.publisher.publish("visiobook.ai.reference.completed", {
            "projectId": project_id,
            "characterId": character_id,
            "referenceImageUrl": image_url
        })

    # ── Référence lieu ────────────────────────────────────────

    async def _handle_location_reference(self, metadata, output):
        """Image de référence du lieu générée → upload + publie"""
        location_id = metadata["location_id"]
        project_id = metadata["project_id"]

        image_url = await self._upload_image(
            output, f"projects/{project_id}/locations/{location_id}/reference.png"
        )

        await self.publisher.publish("visiobook.ai.reference.completed", {
            "projectId": project_id,
            "locationId": location_id,
            "referenceImageUrl": image_url
        })

    # ── Image de scène ────────────────────────────────────────

    async def _handle_scene_image(self, metadata, output):
        """Image de scène générée → upload + publie + LANCE LA VIDÉO"""
        scene_id = metadata["scene_id"]
        execution_id = metadata["execution_id"]
        project_id = metadata["project_id"]

        image_url = await self._upload_image(
            output, f"projects/{project_id}/scenes/{scene_id}/image.png"
        )

        # Track le résultat
        self._track_result(scene_id, "image_url", image_url)

        # Publie image completed
        await self.publisher.publish("visiobook.ai.media.image.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "mediaUrl": image_url
        })

        # ENCHAÎNE : lance la vidéo avec cette image
        video_prompt = metadata["video_prompt"]
        await self._launch_video(
            scene_id=scene_id,
            image_url=image_url,
            video_prompt=video_prompt,
            execution_id=execution_id,
            project_id=project_id
        )

    # ── Vidéo de scène ────────────────────────────────────────

    async def _handle_scene_video(self, metadata, output):
        """Vidéo de scène générée → upload + publie + vérifie si assemblage possible"""
        scene_id = metadata["scene_id"]
        execution_id = metadata["execution_id"]
        project_id = metadata["project_id"]

        video_url = await self._upload_file(
            output, f"projects/{project_id}/scenes/{scene_id}/video.webp", "image/webp"
        )

        self._track_result(scene_id, "video_url", video_url)

        await self.publisher.publish("visiobook.ai.media.video.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "mediaUrl": video_url
        })

        # Vérifie si on peut assembler (vidéo + musique + sfx tous prêts)
        await self._try_assemble(scene_id, execution_id, project_id)

    # ── Musique ───────────────────────────────────────────────

    async def _handle_scene_music(self, metadata, output):
        scene_id = metadata["scene_id"]
        execution_id = metadata["execution_id"]
        project_id = metadata["project_id"]

        music_url = await self._upload_file(
            output, f"projects/{project_id}/scenes/{scene_id}/music.flac", "audio/flac"
        )

        self._track_result(scene_id, "music_url", music_url)

        await self.publisher.publish("visiobook.ai.media.audio.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "type": "music",
            "mediaUrl": music_url
        })

        await self._try_assemble(scene_id, execution_id, project_id)

    # ── SFX ───────────────────────────────────────────────────

    async def _handle_scene_sfx(self, metadata, output):
        scene_id = metadata["scene_id"]
        execution_id = metadata["execution_id"]
        project_id = metadata["project_id"]

        sfx_url = await self._upload_file(
            output, f"projects/{project_id}/scenes/{scene_id}/sfx.flac", "audio/flac"
        )

        self._track_result(scene_id, "sfx_url", sfx_url)

        await self.publisher.publish("visiobook.ai.media.audio.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "type": "sfx",
            "mediaUrl": sfx_url
        })

        await self._try_assemble(scene_id, execution_id, project_id)

    # ── Assemblage ────────────────────────────────────────────

    async def _try_assemble(self, scene_id, execution_id, project_id):
        """Vérifie si tous les médias sont prêts et lance l'assemblage ffmpeg"""
        results = self._scene_results.get(scene_id, {})

        required = {"video_url", "music_url", "sfx_url"}
        if not required.issubset(results.keys()):
            return  # pas encore tout reçu, on attend

        # Tous les médias sont prêts → assemblage
        final_url = await assemble_scene(
            video_url=results["video_url"],
            music_url=results["music_url"],
            sfx_url=results["sfx_url"],
            storage=self.storage,
            output_path=f"projects/{project_id}/scenes/{scene_id}/final.mp4"
        )

        await self.publisher.publish("visiobook.ai.media.scene.completed", {
            "executionId": execution_id,
            "sceneId": scene_id,
            "finalVideoUrl": final_url,
            "imageUrl": results.get("image_url"),
            "videoUrl": results["video_url"],
            "musicUrl": results["music_url"],
            "sfxUrl": results["sfx_url"]
        })

        # Nettoyage mémoire
        del self._scene_results[scene_id]

    # ── Utilitaires ───────────────────────────────────────────

    def _track_result(self, scene_id: str, key: str, value: str):
        if scene_id not in self._scene_results:
            self._scene_results[scene_id] = {}
        self._scene_results[scene_id][key] = value

    async def _upload_image(self, output, path):
        image_data = output["images"][0]
        upload_url = await self.storage.get_upload_url(path, "image/png")
        if image_data["type"] == "base64":
            import base64
            data = base64.b64decode(image_data["data"])
            await self.storage.upload_file(upload_url, data, "image/png")
        return path  # retourne le chemin MinIO

    async def _upload_file(self, output, path, content_type):
        upload_url = await self.storage.get_upload_url(path, content_type)
        # ... upload selon le format de sortie RunPod
        return path

    async def _launch_video(self, scene_id, image_url, video_prompt, execution_id, project_id):
        from app.workflows import wan_video
        workflow = wan_video.build(
            image_url=image_url,
            prompt=video_prompt,
            width=self.settings.DEFAULT_VIDEO_WIDTH,
            height=self.settings.DEFAULT_VIDEO_HEIGHT,
            length=self.settings.DEFAULT_VIDEO_LENGTH
        )
        await self.runpod.submit_job(
            endpoint_id=self.settings.RUNPOD_ENDPOINT_VIDEO,
            workflow=workflow,
            metadata={
                "job_type": "scene_video",
                "scene_id": scene_id,
                "execution_id": execution_id,
                "project_id": project_id
            }
        )

    async def _handle_failure(self, metadata, error):
        await self.publisher.publish("visiobook.ai.media.failed", {
            "executionId": metadata.get("execution_id"),
            "sceneId": metadata.get("scene_id"),
            "step": metadata.get("job_type"),
            "error": str(error),
            "retryCount": metadata.get("retry_count", 0)
        })
```

---

## 8. Handlers NATS

### 8.1 Reference Handler

```python
# app/handlers/reference_handler.py

class ReferenceHandler:
    def __init__(self, runpod, publisher, settings):
        self.runpod = runpod
        self.publisher = publisher
        self.settings = settings

    async def handle(self, data: dict):
        """Génère les images de référence pour les nouveaux personnages et lieux."""
        project_id = data["projectId"]
        book_style = data["bookStyle"]

        # Personnages
        for char in data.get("characters", []):
            from app.workflows import flux_portrait
            workflow = flux_portrait.build(
                physical_description=char["physicalDescription"],
                visual_style=book_style["visualStyle"],
                negative_prompt=book_style["negativePrompt"]
            )
            await self.runpod.submit_job(
                endpoint_id=self.settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                metadata={
                    "job_type": "character_reference",
                    "character_id": char["characterId"],
                    "project_id": project_id
                }
            )

        # Lieux
        for loc in data.get("locations", []):
            from app.workflows import flux_location
            workflow = flux_location.build(
                location_description=loc["description"],
                visual_style=book_style["visualStyle"],
                negative_prompt=book_style["negativePrompt"]
            )
            await self.runpod.submit_job(
                endpoint_id=self.settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                metadata={
                    "job_type": "location_reference",
                    "location_id": loc["locationId"],
                    "project_id": project_id
                }
            )

        await self.publisher.publish("visiobook.ai.progress", {
            "executionId": data.get("executionId"),
            "step": "reference_generation",
            "progress": 10,
            "message": f"Generating {len(data.get('characters', []))} character(s) and {len(data.get('locations', []))} location(s)"
        })
```

### 8.2 Scene Handler

```python
# app/handlers/scene_handler.py

class SceneHandler:
    def __init__(self, runpod, publisher, settings):
        self.runpod = runpod
        self.publisher = publisher
        self.settings = settings

    async def handle(self, data: dict):
        """Génère les images pour toutes les scènes d'un projet."""
        book_style = data["bookStyle"]
        characters = {c["name"]: c for c in data.get("characters", [])}
        # Indexe aussi par alias
        for char in data.get("characters", []):
            for alias in char.get("aliases", []):
                characters[alias] = char

        locations = {loc["name"]: loc for loc in data.get("locations", [])}
        scenes = data["scenes"]

        for i, scene in enumerate(scenes):
            # Trouve les personnages présents dans cette scène
            scene_char_refs = []
            for char_name in scene.get("charactersPresent", []):
                char = characters.get(char_name)
                if char and char.get("referenceImageUrl"):
                    scene_char_refs.append(char)

            # Trouve le lieu
            location_ref = None
            if scene.get("location"):
                loc = locations.get(scene["location"])
                if loc and loc.get("referenceImageUrl"):
                    location_ref = loc

            # Construit le prompt final
            full_prompt = f"{book_style['visualStyle']}, {scene['prompts']['image']}"
            full_negative = f"{book_style.get('negativePrompt', '')}, {scene['prompts'].get('imageNegative', '')}"

            # Choisit le workflow
            if scene_char_refs:
                from app.workflows import flux_scene_ipadapter
                workflow = flux_scene_ipadapter.build(
                    prompt=full_prompt,
                    negative_prompt=full_negative,
                    character_ref_url=scene_char_refs[0]["referenceImageUrl"],
                    location_ref_url=location_ref["referenceImageUrl"] if location_ref else None
                )
            else:
                from app.workflows import flux_scene
                workflow = flux_scene.build(
                    prompt=full_prompt,
                    negative_prompt=full_negative
                )

            await self.runpod.submit_job(
                endpoint_id=self.settings.RUNPOD_ENDPOINT_IMAGE,
                workflow=workflow,
                metadata={
                    "job_type": "scene_image",
                    "scene_id": scene["sceneId"],
                    "execution_id": data["executionId"],
                    "project_id": data["projectId"],
                    "video_prompt": scene["prompts"]["video"]
                }
            )

            await self.publisher.publish("visiobook.ai.progress", {
                "executionId": data["executionId"],
                "step": "image_generation",
                "progress": int((i + 1) / len(scenes) * 15),
                "message": f"Queued image {i+1}/{len(scenes)}"
            })
```

### 8.3 Audio Handler

```python
# app/handlers/audio_handler.py

class AudioHandler:
    def __init__(self, runpod, publisher, settings):
        self.runpod = runpod
        self.publisher = publisher
        self.settings = settings

    async def handle(self, data: dict):
        """Lance musique + SFX en parallèle pour chaque scène."""
        book_style = data["bookStyle"]
        scenes = data["scenes"]

        for scene in scenes:
            # Musique (ACE-Step)
            from app.workflows import ace_step_music
            music_tags = f"{book_style.get('musicGenre', '')}, {scene['prompts']['musicTags']}"
            music_workflow = ace_step_music.build(
                tags=music_tags,
                duration_sec=scene.get("duration", 30)
            )
            await self.runpod.submit_job(
                endpoint_id=self.settings.RUNPOD_ENDPOINT_AUDIO,
                workflow=music_workflow,
                metadata={
                    "job_type": "scene_music",
                    "scene_id": scene["sceneId"],
                    "execution_id": data["executionId"],
                    "project_id": data["projectId"]
                }
            )

            # SFX (Stable Audio)
            from app.workflows import stable_audio_sfx
            sfx_workflow = stable_audio_sfx.build(
                prompt=scene["prompts"]["sfx"],
                duration_sec=scene.get("duration", 30)
            )
            await self.runpod.submit_job(
                endpoint_id=self.settings.RUNPOD_ENDPOINT_AUDIO,
                workflow=sfx_workflow,
                metadata={
                    "job_type": "scene_sfx",
                    "scene_id": scene["sceneId"],
                    "execution_id": data["executionId"],
                    "project_id": data["projectId"]
                }
            )
```

---

## 9. NATS Consumer

```python
# app/nats/consumer.py
import json
import nats

class NATSConsumer:
    def __init__(self, settings, reference_handler, scene_handler, audio_handler):
        self.settings = settings
        self.reference_handler = reference_handler
        self.scene_handler = scene_handler
        self.audio_handler = audio_handler

    async def start(self):
        self.nc = await nats.connect(self.settings.NATS_URL)
        self.js = self.nc.jetstream()

        await self.js.subscribe(
            "visiobook.media.generate_references",
            cb=self._on_generate_references,
            durable="ai-media-gen-refs",
            stream=self.settings.NATS_STREAM
        )
        await self.js.subscribe(
            "visiobook.workflow.step.image_generation",
            cb=self._on_image_generation,
            durable="ai-media-gen-image",
            stream=self.settings.NATS_STREAM
        )
        await self.js.subscribe(
            "visiobook.workflow.step.audio_generation",
            cb=self._on_audio_generation,
            durable="ai-media-gen-audio",
            stream=self.settings.NATS_STREAM
        )

    async def _on_generate_references(self, msg):
        try:
            data = json.loads(msg.data)
            await self.reference_handler.handle(data)
            await msg.ack()
        except Exception as e:
            await msg.nak(delay=5)

    async def _on_image_generation(self, msg):
        try:
            data = json.loads(msg.data)
            await self.scene_handler.handle(data)
            await msg.ack()
        except Exception as e:
            await msg.nak(delay=5)

    async def _on_audio_generation(self, msg):
        try:
            data = json.loads(msg.data)
            await self.audio_handler.handle(data)
            await msg.ack()
        except Exception as e:
            await msg.nak(delay=5)

    async def stop(self):
        if self.nc:
            await self.nc.drain()
```

---

## 10. Assemblage ffmpeg

```python
# app/assembler/ffmpeg.py
import asyncio
import tempfile
import os

async def assemble_scene(
    video_url: str,
    music_url: str,
    sfx_url: str,
    storage,
    output_path: str
) -> str:
    """
    Télécharge vidéo + audio, mixe avec ffmpeg, upload le résultat.
    Pas de GPU nécessaire.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        # Télécharge les fichiers depuis MinIO
        video_path = os.path.join(tmpdir, "video.webp")
        music_path = os.path.join(tmpdir, "music.flac")
        sfx_path = os.path.join(tmpdir, "sfx.flac")
        output_file = os.path.join(tmpdir, "final.mp4")

        await storage.download_file(video_url, video_path)
        await storage.download_file(music_url, music_path)
        await storage.download_file(sfx_url, sfx_path)

        # Mixe musique + SFX à 50/50, puis combine avec vidéo
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", music_path,
            "-i", sfx_path,
            "-filter_complex",
            "[1:a]volume=0.6[music];[2:a]volume=0.4[sfx];[music][sfx]amix=inputs=2:duration=shortest[audio]",
            "-map", "0:v",
            "-map", "[audio]",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            output_file
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {stderr.decode()}")

        # Upload le résultat
        upload_url = await storage.get_upload_url(output_path, "video/mp4")
        with open(output_file, "rb") as f:
            await storage.upload_file(upload_url, f.read(), "video/mp4")

        return output_path
```

---

## 11. Workflow Builders (construction des JSON ComfyUI)

### 11.1 Portrait de référence personnage

```python
# app/workflows/flux_portrait.py
import json, copy
from pathlib import Path

TEMPLATE = json.loads(Path("workflow_templates/flux_portrait.json").read_text())

def build(physical_description: str, visual_style: str, negative_prompt: str) -> dict:
    workflow = copy.deepcopy(TEMPLATE)

    prompt = (
        f"portrait of {physical_description}, "
        f"face clearly visible, looking at camera, neutral background, "
        f"well lit, {visual_style}, "
        f"upper body shot, detailed face, high quality"
    )

    workflow["6"]["inputs"]["text"] = prompt
    workflow["7"]["inputs"]["text"] = f"back view, profile, {negative_prompt}"

    return workflow
```

### 11.2 Scène avec IP-Adapter (cohérence personnage)

```python
# app/workflows/flux_scene_ipadapter.py

def build(
    prompt: str,
    negative_prompt: str,
    character_ref_url: str,
    location_ref_url: str = None
) -> dict:
    workflow = copy.deepcopy(TEMPLATE)

    workflow["positive_prompt"]["inputs"]["text"] = prompt
    workflow["negative_prompt"]["inputs"]["text"] = negative_prompt
    workflow["ipadapter_image"]["inputs"]["url"] = character_ref_url

    if location_ref_url:
        workflow["composition_image"]["inputs"]["url"] = location_ref_url

    return workflow
```

### 11.3 Vidéo Wan 2.1 I2V

```python
# app/workflows/wan_video.py

def build(image_url: str, prompt: str, width=832, height=480, length=81) -> dict:
    workflow = copy.deepcopy(TEMPLATE)

    workflow["load_image"]["inputs"]["image"] = image_url
    workflow["clip_text"]["inputs"]["text"] = prompt
    workflow["wan_i2v"]["inputs"]["width"] = width
    workflow["wan_i2v"]["inputs"]["height"] = height
    workflow["wan_i2v"]["inputs"]["length"] = length

    return workflow
```

### 11.4 Musique ACE-Step

```python
# app/workflows/ace_step_music.py

def build(tags: str, duration_sec: int = 30, lyrics: str = "") -> dict:
    workflow = copy.deepcopy(TEMPLATE)

    workflow["text_encode"]["inputs"]["tags"] = tags
    workflow["text_encode"]["inputs"]["lyrics"] = lyrics
    workflow["empty_latent"]["inputs"]["duration"] = duration_sec

    return workflow
```

### 11.5 SFX Stable Audio

```python
# app/workflows/stable_audio_sfx.py

def build(prompt: str, duration_sec: int = 30) -> dict:
    workflow = copy.deepcopy(TEMPLATE)

    workflow["text_encode"]["inputs"]["text"] = prompt
    workflow["empty_latent"]["inputs"]["seconds"] = duration_sec

    return workflow
```

---

## 12. Entrypoint (main.py)

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.config import Settings
from app.nats.consumer import NATSConsumer
from app.nats.publisher import NATSPublisher
from app.clients.runpod import RunPodClient
from app.clients.storage import StorageServiceClient
from app.handlers.reference_handler import ReferenceHandler
from app.handlers.scene_handler import SceneHandler
from app.handlers.audio_handler import AudioHandler
from app.handlers.webhook_handler import WebhookHandler
from app.api.webhooks import router as webhook_router
from app.api.health import router as health_router

settings = Settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    publisher = NATSPublisher(settings)
    await publisher.connect()

    storage = StorageServiceClient(settings.STORAGE_URL)
    runpod = RunPodClient(settings.RUNPOD_API_KEY, settings.WEBHOOK_BASE_URL)

    # Handlers
    ref_handler = ReferenceHandler(runpod, publisher, settings)
    scene_handler = SceneHandler(runpod, publisher, settings)
    audio_handler = AudioHandler(runpod, publisher, settings)
    webhook_handler = WebhookHandler(runpod, storage, publisher, settings)

    # NATS consumer
    consumer = NATSConsumer(settings, ref_handler, scene_handler, audio_handler)
    await consumer.start()

    # Expose pour le webhook endpoint
    app.state.webhook_handler = webhook_handler
    app.state.publisher = publisher

    yield

    # Shutdown
    await consumer.stop()
    await publisher.disconnect()

app = FastAPI(title="ai-media-generation-service", version="2.0.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(health_router)
```

---

## 13. Docker

### Dockerfile

```dockerfile
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY workflow_templates/ ./workflow_templates/

EXPOSE 8087

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8087"]
```

### requirements.txt

```
fastapi==0.115.*
uvicorn[standard]==0.34.*
httpx==0.28.*
nats-py==2.9.*
pydantic==2.10.*
pydantic-settings==2.7.*
tenacity==9.*
```

### docker-compose.yml (extrait)

```yaml
services:
  ai-media-generation:
    build: ./ai-media-generation-service
    ports:
      - "8087:8087"
    environment:
      - NATS_URL=nats://nats:4222
      - STORAGE_URL=http://storage-service:8085
      - RUNPOD_API_KEY=${RUNPOD_API_KEY}
      - RUNPOD_ENDPOINT_IMAGE=${RUNPOD_ENDPOINT_IMAGE}
      - RUNPOD_ENDPOINT_VIDEO=${RUNPOD_ENDPOINT_VIDEO}
      - RUNPOD_ENDPOINT_AUDIO=${RUNPOD_ENDPOINT_AUDIO}
      - WEBHOOK_BASE_URL=${WEBHOOK_BASE_URL}
    depends_on:
      - nats
      - storage-service
    networks:
      - visiobook
    restart: unless-stopped
```

---

## 14. RunPod Serverless — Configuration

### 3 Endpoints

| Endpoint | GPU | Flex Workers | Active Workers | Idle Timeout |
|----------|-----|-------------|----------------|-------------|
| Image | L40S 48GB | 0 → 5 | 0 | 60 sec |
| Vidéo | A100 80GB | 0 → 3 | 0 | 60 sec |
| Audio | L40S 48GB | 0 → 5 | 0 | 30 sec |

### Network Volume (~95 Go)

```
/runpod-volume/models/
├── diffusion_models/
│   ├── flux2_dev_fp16.safetensors              # 23 Go — images
│   └── wan2.1_i2v_480p_14B_fp16.safetensors    # 31 Go — vidéo
├── checkpoints/
│   ├── juggernautXL_v9.safetensors             # 6.7 Go — base SDXL pour IP-Adapter
│   ├── ace_step_v1_3.5b.safetensors            # 7.7 Go — musique
│   └── stable_audio_open_1.0.safetensors       # 1.1 Go — SFX
├── text_encoders/
│   ├── t5xxl_fp16.safetensors                  # 9.3 Go
│   ├── clip_l.safetensors                      # 235 Mo
│   └── umt5_xxl_fp16.safetensors               # 10.8 Go
├── vae/
│   ├── ae.safetensors                          # 335 Mo
│   └── wan_2.1_vae.safetensors                 # 254 Mo
├── clip_vision/
│   └── clip_vision_h.safetensors               # 2.4 Go
└── ipadapter/
    ├── ip-adapter-faceid-plusv2_sdxl.bin        # 1.4 Go
    └── ip-adapter-faceid-plusv2_sdxl_lora.safetensors
```

### Docker Image ComfyUI (pour les workers RunPod)

```dockerfile
FROM runpod/worker-comfyui:latest-base

RUN cd /comfyui/custom_nodes && \
    git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus.git && \
    cd ComfyUI_IPAdapter_plus && pip install -r requirements.txt

RUN pip install insightface onnxruntime-gpu

COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml
```

---

## 15. Graphe de dépendances par scène

```
Séquence 1 : Image (~10 sec GPU)
    input  : bookStyle.visualStyle + scene.prompts.image + character referenceImageUrl
    output : image.png → MinIO
    │
    ├──────────────────────────┐
    ▼                          │  (en parallèle, pas de dépendance sur la vidéo)
Séquence 2 : Vidéo (~3-4 min) │
    input  : image.png +       │
             scene.prompts.video│
    output : video.webp → MinIO│
    │                          │
    │      Séquence 3 : Musique (~20 sec)
    │          input  : bookStyle.musicGenre + scene.prompts.musicTags
    │          output : music.flac → MinIO
    │          │
    │      Séquence 4 : SFX (~10 sec)
    │          input  : scene.prompts.sfx
    │          output : sfx.flac → MinIO
    │          │
    ▼          ▼
    ┌──────────────────────────┐
    │ Séquence 5 : Assemblage  │
    │ (ffmpeg, pas de GPU)     │
    │ Attend : vidéo + musique + sfx
    │ output : final.mp4 → MinIO
    └──────────────────────────┘
               │
               ▼
    visiobook.ai.media.scene.completed

Temps total chemin critique : ~4-5 min par scène
(musique + SFX en parallèle de la vidéo → pas de temps ajouté)
```

---

## 16. Flux complet page par page

```
UTILISATEUR scanne la page 1
         │
         ▼
    core-project-service
    │  Envoie le texte à l'ai-analysis-service
    │
         ▼
    ai-analysis-service
    │  Analyse le texte
    │  Retourne : scènes, personnages, ambiance, prompts
    │
         ▼
    core-project-service
    │  Reçoit l'analyse
    │  Pour chaque personnage détecté :
    │    SELECT FROM Character WHERE name = ? OR aliases @> ?
    │    → Trouvé ? → Réutilise (déjà une referenceImageUrl)
    │    → Pas trouvé ? → INSERT avec referenceStatus = "needs_reference"
    │  Pour chaque lieu :
    │    Même logique de matching
    │
    │  Si nouveaux personnages/lieux sans référence :
    │    Publie NATS "visiobook.media.generate_references"
    │    { characters: [...], locations: [...], bookStyle: {...} }
    │
         ▼
    ai-media-generation-service
    │  Consomme l'event
    │  Pour chaque personnage → workflow portrait Flux.2 → RunPod
    │  Pour chaque lieu → workflow lieu Flux.2 → RunPod
    │
         ▼
    RunPod GPU (Flex Worker)
    │  Génère les portraits / lieux
    │  Webhook callback
    │
         ▼
    ai-media-generation-service
    │  Upload images → MinIO (via StorageService)
    │  Publie NATS "visiobook.ai.reference.completed"
    │  { characterId, referenceImageUrl }
    │
         ▼
    core-project-service
    │  UPDATE Character SET referenceImageUrl = ?, referenceStatus = "ready"
    │  Vérifie : tous les personnages des scènes sont "ready" ?
    │  → OUI : publie NATS "visiobook.workflow.step.image_generation"
    │          avec TOUTES les refs dans le payload
    │
         ▼
    ai-media-generation-service
    │  Consomme l'event
    │  Pour chaque scène :
    │    1. prompt = bookStyle.visualStyle + scene.prompts.image
    │    2. Si personnage → workflow Flux.2 + IP-Adapter FaceID
    │    3. Sinon → workflow Flux.2 simple
    │    4. POST RunPod endpoint image
    │
         ▼
    RunPod GPU → génère image → webhook
         ▼
    ai-media-generation-service (webhook)
    │  Upload image → MinIO
    │  Publie "visiobook.ai.media.image.completed"
    │  ENCHAÎNE → construit workflow Wan 2.1 I2V → POST RunPod endpoint vidéo
    │
         ▼
    RunPod GPU → génère vidéo (~3-4 min) → webhook
         ▼
    ai-media-generation-service (webhook)
    │  Upload vidéo → MinIO
    │  Publie "visiobook.ai.media.video.completed"
    │  Vérifie si musique + SFX sont prêts → assemblage si oui
    │
         ▼
    core-project-service
    │  Met à jour Scene.generatedImageUrl, Scene.generatedVideoUrl
    │  Quand toutes les scènes image+vidéo OK :
    │  Publie NATS "visiobook.workflow.step.audio_generation"
    │
         ▼
    ai-media-generation-service
    │  Pour chaque scène en parallèle :
    │    ACE-Step → musique → RunPod
    │    Stable Audio → SFX → RunPod
    │
         ▼
    RunPod GPU → génère audio → webhooks
         ▼
    ai-media-generation-service (webhooks)
    │  Upload audio → MinIO
    │  Quand vidéo + musique + SFX tous reçus pour une scène :
    │    → ffmpeg assemble → final.mp4
    │    → Upload → MinIO
    │    → Publie "visiobook.ai.media.scene.completed"
    │
         ▼
    core-project-service
    │  Met à jour Scene avec finalVideoUrl
    │  Quand toutes les scènes sont complètes → étape "assembly" (montage global)

═══════════════════════════════════════════════════

UTILISATEUR scanne la page 2
         │
         ▼
    (même flux, mais cette fois le core-project-service
     retrouve "Le narrateur" en BDD avec sa referenceImageUrl
     → pas de nouvelle génération de référence
     → passe directement à la génération des scènes)
```

---

## 17. Points d'attention production

### Idempotence
Le webhook RunPod peut être appelé plusieurs fois (retry). Utiliser le `job_id` comme clé pour ne pas traiter deux fois le même résultat. Le `_scene_results` dict dans le webhook handler doit gérer les doublons.

### Multi-instance
Le tracking `_scene_results` en mémoire ne fonctionne que si le service tourne en une seule instance. Si tu scales à plusieurs instances, remplace par Redis (simple key-value avec TTL). Les events NATS avec durable subscribers supportent déjà le multi-instance nativement.

### Cold start RunPod
Le premier job après une période d'inactivité prend 30-90 sec. Stratégie : traiter les scènes séquentiellement (pas en batch) pour que le worker reste warm entre les scènes. Pour un livre entier, le cold start ne se paie qu'une seule fois.

### Taille des payloads
RunPod limite les requêtes à 10 Mo. Les images de référence IP-Adapter sont passées par URL (MinIO), pas en base64. Le workflow JSON contient uniquement l'URL, le worker ComfyUI télécharge l'image depuis MinIO.

### Webhook URL publique
En dev : ngrok ou cloudflared tunnel. En prod : le service doit être exposé via l'API Gateway. Ajouter un `WEBHOOK_SECRET` dans l'URL pour valider l'authenticité des callbacks.

### Monitoring
Ajouter un endpoint `/metrics` Prometheus avec : nombre de jobs par type et statut, durée moyenne par séquence, coût estimé par scène, taux d'erreur.

### Timeout et fallback
Si un webhook ne revient pas après 10 minutes, un background task (asyncio periodic) doit poller le statut RunPod en fallback. Configurer un max de 3 retries avec backoff exponentiel.

---

## 18. Estimation des coûts

### Par scène (A100 80GB Flex)

| Séquence | Durée GPU | Coût |
|----------|-----------|------|
| Image Flux.2 | ~10 sec | $0.008 |
| Vidéo Wan 2.1 | ~3-4 min | $0.137 |
| Musique ACE-Step | ~20 sec | $0.015 |
| SFX Stable Audio | ~10 sec | $0.008 |
| **Total** | **~4-5 min** | **~$0.17** |

### Par livre

| Taille | Coût GPU | Temps total |
|--------|----------|-------------|
| 20 scènes | ~$3.40 | ~1.5h |
| 50 scènes | ~$8.50 | ~4h |
| 200 scènes | ~$34 | ~15h |

### Coûts fixes

| Composant | Coût |
|-----------|------|
| Network Volume 100 Go | $7/mois |
| 1 Active Worker (optionnel) | ~$14/jour |
