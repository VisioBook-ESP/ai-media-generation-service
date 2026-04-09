#!/usr/bin/env bash
set -euo pipefail

BASE_IMAGE="vattv/visiobook-comfyui"
REPO_DIR="/tmp/worker-comfyui"
COMFYUI_VERSION="v0.18.5"

VERSION_FILE="$(dirname "$0")/.docker_version"
VERSION=$(( $(cat "$VERSION_FILE" 2>/dev/null || echo 0) + 1 ))
echo "$VERSION" > "$VERSION_FILE"
TAG="v$VERSION"
IMAGE="$BASE_IMAGE:$TAG"

echo "=== [1/4] Clone worker-comfyui ==="
if [[ -d "$REPO_DIR/.git" ]]; then
  echo "  Réutilisation du clone existant (reset + git pull)"
  git -C "$REPO_DIR" checkout -- Dockerfile
  git -C "$REPO_DIR" pull --ff-only
else
  rm -rf "$REPO_DIR"
  git clone --depth 1 https://github.com/runpod-workers/worker-comfyui.git "$REPO_DIR"
fi

echo ""
echo "=== [2/4] Patch Dockerfile + extra_model_paths.yaml ==="
python3 - <<PY
from pathlib import Path
dockerfile = Path("$REPO_DIR/Dockerfile")
text = dockerfile.read_text()
old = "ARG COMFYUI_VERSION=latest"
new = "ARG COMFYUI_VERSION=$COMFYUI_VERSION"
if old not in text:
    raise SystemExit("Expected COMFYUI_VERSION arg not found in worker Dockerfile")
dockerfile.write_text(text.replace(old, new, 1))
PY

cp "$(dirname "$0")/../extra_model_paths.yaml" "$REPO_DIR/extra_model_paths.yaml"
cp "$(dirname "$0")/patch_pulidflux.py" "$REPO_DIR/patch_pulidflux.py"

# Append custom layers — each RUN is a separate layer to keep push sizes manageable
cat >> "$REPO_DIR/Dockerfile" <<'DOCKER'

# ── Extra model paths ────────────────────────────────────────────────────────
COPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml

# ── ComfyUI deps (pinned to avoid torch upgrade) ────────────────────────────
RUN /opt/venv/bin/pip freeze > /tmp/freeze.txt \
    && grep -vxE 'torch|torchvision|torchaudio' /comfyui/requirements.txt > /tmp/reqs.txt \
    && /opt/venv/bin/pip install -r /tmp/reqs.txt -c /tmp/freeze.txt \
    && rm /tmp/freeze.txt /tmp/reqs.txt

# ── torchaudio (required by LTXVideo) ───────────────────────────────────────
RUN /opt/venv/bin/pip install torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128

# ── Custom nodes ─────────────────────────────────────────────────────────────
RUN cd /comfyui/custom_nodes && git clone https://github.com/zhangp365/ComfyUI-PuLID-Flux.git
RUN cd /comfyui/custom_nodes && git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git

# ── PuLID patch ──────────────────────────────────────────────────────────────
COPY patch_pulidflux.py /tmp/patch_pulidflux.py
RUN /opt/venv/bin/python /tmp/patch_pulidflux.py && rm /tmp/patch_pulidflux.py

# ── PuLID dependencies ───────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends g++ python3.12-dev \
    && rm -rf /var/lib/apt/lists/*
RUN /opt/venv/bin/pip install facexlib ftfy timm onnxruntime-gpu insightface==0.7.3 einops torchsde

# ── Model symlinks (resolved at runtime from volume) ─────────────────────────
RUN mkdir -p /comfyui/models/clip /comfyui/models/insightface/models \
    && ln -sfn /runpod-volume/models/text_encoders/EVA02_CLIP_L_336_psz14_s6B.pt /comfyui/models/clip/EVA02_CLIP_L_336_psz14_s6B.pt \
    && ln -sfn /runpod-volume/models/insightface/models/antelopev2 /comfyui/models/insightface/models/antelopev2
DOCKER

echo ""
echo "=== [3/4] Build Docker image ==="
cd "$REPO_DIR"
PREV_TAG="v$(( VERSION - 1 ))"
docker build --cache-from "$BASE_IMAGE:$PREV_TAG" -t "$IMAGE" .

echo ""
echo "=== [4/4] Verify & Push ==="
docker run --rm "$IMAGE" cat /comfyui/extra_model_paths.yaml
docker run --rm "$IMAGE" test -d /comfyui/custom_nodes/ComfyUI-PuLID-Flux
docker run --rm "$IMAGE" test -d /comfyui/custom_nodes/ComfyUI-LTXVideo
docker run --rm "$IMAGE" sh -lc "grep -q 'timestep_zero_index' /comfyui/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py && echo 'PuLID patch: OK'"

echo "Pushing $IMAGE (this may take a while)..."
docker push "$IMAGE"

echo ""
echo "Done. Image pushed: $IMAGE"
echo "→ Update setup_pod.yaml image to: $IMAGE"
