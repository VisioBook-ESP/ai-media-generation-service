#!/usr/bin/env bash
set -euo pipefail

IMAGE="vattv/visiobook-comfyui:latest"
REPO_DIR="/tmp/worker-comfyui"

echo "=== [1/4] Clone worker-comfyui ==="
rm -rf "$REPO_DIR"
git clone https://github.com/runpod-workers/worker-comfyui.git "$REPO_DIR"

echo ""
echo "=== [2/4] Copy extra_model_paths.yaml ==="
cp "$(dirname "$0")/../extra_model_paths.yaml" "$REPO_DIR/extra_model_paths.yaml"

echo ""
echo "=== [3/4] Build Docker image ==="
cd "$REPO_DIR"
docker build --no-cache -t "$IMAGE" .

echo ""
echo "=== [4/4] Verify & Push ==="
docker run --rm "$IMAGE" cat /comfyui/extra_model_paths.yaml
docker push "$IMAGE"

echo ""
echo "Done. Image pushed : $IMAGE"
