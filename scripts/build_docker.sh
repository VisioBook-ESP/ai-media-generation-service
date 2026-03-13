#!/usr/bin/env bash
set -euo pipefail

BASE_IMAGE="vattv/visiobook-comfyui"
REPO_DIR="/tmp/worker-comfyui"

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
cp "$(dirname "$0")/../extra_model_paths.yaml" "$REPO_DIR/extra_model_paths.yaml"
printf "\nCOPY extra_model_paths.yaml /comfyui/extra_model_paths.yaml\n" >> "$REPO_DIR/Dockerfile"
printf "RUN cd /comfyui/custom_nodes && git clone https://github.com/cubiq/PuLID_ComfyUI\n" >> "$REPO_DIR/Dockerfile"
printf "RUN /opt/venv/bin/pip install insightface facexlib onnxruntime-gpu timm einops ftfy\n" >> "$REPO_DIR/Dockerfile"

echo ""
echo "=== [3/4] Build Docker image ==="
cd "$REPO_DIR"
PREV_TAG="v$(( VERSION - 1 ))"
docker build --cache-from "$BASE_IMAGE:$PREV_TAG" -t "$IMAGE" .

echo ""
echo "=== [4/4] Verify & Push ==="
docker run --rm "$IMAGE" cat /comfyui/extra_model_paths.yaml
docker push "$IMAGE"

echo ""
echo "Done. Image pushed : $IMAGE"
echo ""
echo "→ Tag à utiliser dans RunPod New Release : $IMAGE"
