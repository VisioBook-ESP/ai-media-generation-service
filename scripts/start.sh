#!/usr/bin/env bash
cd /comfyui && /opt/venv/bin/python main.py \
  --listen 0.0.0.0 \
  --port 8188 \
  --extra-model-paths-config /comfyui/extra_model_paths.yaml \
  || sleep infinity
