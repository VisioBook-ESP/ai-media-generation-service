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
printf "\nCOPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml\n" >> "$REPO_DIR/Dockerfile"
printf "RUN /opt/venv/bin/pip freeze > /tmp/freeze.txt && grep -vxE 'torch|torchvision|torchaudio' /comfyui/requirements.txt > /tmp/reqs.txt && /opt/venv/bin/pip install -r /tmp/reqs.txt -c /tmp/freeze.txt\n" >> "$REPO_DIR/Dockerfile"
printf "RUN /opt/venv/bin/pip install torchaudio==2.10.0 --index-url https://download.pytorch.org/whl/cu128\n" >> "$REPO_DIR/Dockerfile"
printf "RUN cd /comfyui/custom_nodes && git clone https://github.com/zhangp365/ComfyUI-PuLID-Flux.git\n" >> "$REPO_DIR/Dockerfile"
printf "RUN cd /comfyui/custom_nodes && git clone https://github.com/Lightricks/ComfyUI-LTXVideo.git\n" >> "$REPO_DIR/Dockerfile"
cp "$(dirname "$0")/patch_pulidflux.py" "$REPO_DIR/patch_pulidflux.py"
printf "COPY patch_pulidflux.py /tmp/patch_pulidflux.py\n" >> "$REPO_DIR/Dockerfile"
printf "RUN /opt/venv/bin/python /tmp/patch_pulidflux.py\n" >> "$REPO_DIR/Dockerfile"
printf "RUN apt-get update && apt-get install -y --no-install-recommends g++ python3.12-dev && rm -rf /var/lib/apt/lists/*\n" >> "$REPO_DIR/Dockerfile"
printf "RUN /opt/venv/bin/pip install facexlib ftfy timm onnxruntime-gpu insightface==0.7.3 einops torchsde\n" >> "$REPO_DIR/Dockerfile"
printf "RUN mkdir -p /comfyui/models/clip /comfyui/models/insightface/models\n" >> "$REPO_DIR/Dockerfile"
printf "RUN ln -sfn /runpod-volume/models/text_encoders/EVA02_CLIP_L_336_psz14_s6B.pt /comfyui/models/clip/EVA02_CLIP_L_336_psz14_s6B.pt\n" >> "$REPO_DIR/Dockerfile"
printf "RUN ln -sfn /runpod-volume/models/insightface/models/antelopev2 /comfyui/models/insightface/models/antelopev2\n" >> "$REPO_DIR/Dockerfile"

echo ""
echo "=== [3/4] Build Docker image ==="
cd "$REPO_DIR"
PREV_TAG="v$(( VERSION - 1 ))"
docker build --cache-from "$BASE_IMAGE:$PREV_TAG" -t "$IMAGE" .

echo ""
echo "=== [4/4] Verify & Push ==="
docker run --rm "$IMAGE" cat /comfyui/extra_model_paths.yaml
docker run --rm "$IMAGE" test -d /comfyui/custom_nodes/ComfyUI-PuLID-Flux
docker run --rm "$IMAGE" sh -lc "grep -R \"ApplyPulidFlux\\|PulidFluxModelLoader\" /comfyui/custom_nodes/ComfyUI-PuLID-Flux >/dev/null"
docker run --rm "$IMAGE" sh -lc "test -L /comfyui/models/clip/EVA02_CLIP_L_336_psz14_s6B.pt"
docker run --rm "$IMAGE" sh -lc "test -L /comfyui/models/insightface/models/antelopev2"
docker run --rm "$IMAGE" sh -lc "cd /comfyui/custom_nodes/ComfyUI-PuLID-Flux && git rev-parse HEAD"
docker run --rm "$IMAGE" test -d /comfyui/custom_nodes/ComfyUI-LTXVideo
docker run --rm "$IMAGE" sh -lc "grep -q 'timestep_zero_index' /comfyui/custom_nodes/ComfyUI-PuLID-Flux/pulidflux.py && echo 'PuLID patch: OK' || (echo 'PuLID patch: MISSING' && exit 1)"
docker push "$IMAGE"

echo ""
echo "Done. Image pushed : $IMAGE"
echo ""
echo "→ Tag à utiliser dans RunPod New Release : $IMAGE"
