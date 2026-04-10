#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Script de setup complet du network volume RunPod
# Usage : HF_TOKEN=hf_xxx bash setup_models.sh
#
# Lancer depuis un pod RunPod avec le volume Visiobook attaché à /runpod-volume
# =============================================================================

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "Erreur : HF_TOKEN non défini."
  echo "Usage : HF_TOKEN=hf_xxx bash setup_models.sh"
  exit 1
fi

if ! df -h /runpod-volume &>/dev/null; then
  echo "Erreur : /runpod-volume n'est pas monté."
  exit 1
fi

MODELS="/runpod-volume/models"

# ── Création de la structure de dossiers ──────────────────────────────────────

mkdir -p "$MODELS/diffusion_models"
mkdir -p "$MODELS/text_encoders"
mkdir -p "$MODELS/vae"
mkdir -p "$MODELS/checkpoints"
mkdir -p "$MODELS/clip_vision"
mkdir -p "$MODELS/style_models"
mkdir -p "$MODELS/loras"
mkdir -p "$MODELS/latent_upscale_models"

echo "Structure créée dans $MODELS"
echo ""

# ── Helper ────────────────────────────────────────────────────────────────────

dl() {
  local url="$1"
  local dest="$2"
  local auth="${3:-}"

  if [[ -f "$dest" ]] && [[ -s "$dest" ]]; then
    echo "  [SKIP] $(basename "$dest") — déjà présent ($(du -sh "$dest" | cut -f1))"
    return
  fi
  [[ -f "$dest" ]] && rm "$dest"

  echo "  [DL]   $(basename "$dest")"
  if [[ -n "$auth" ]]; then
    wget -q --show-progress --header="Authorization: Bearer $auth" "$url" -O "$dest"
  else
    wget -q --show-progress "$url" -O "$dest"
  fi
  echo "  [OK]   $(basename "$dest") — $(du -sh "$dest" | cut -f1)"
}

# ── 1. FLUX.1-dev — modèle principal images ───────────────────────────────────

echo "=== [1/6] Flux.1-dev fp16 (~23 Go) ==="

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors" \
  "$MODELS/diffusion_models/flux1_dev_fp16.safetensors" \
  "$HF_TOKEN"

# ── 2. Text encoders Flux ────────────────────────────────────────────────────

echo ""
echo "=== [2/6] Text encoders Flux ==="

dl \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" \
  "$MODELS/text_encoders/t5xxl_fp16.safetensors"

dl \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
  "$MODELS/text_encoders/clip_l.safetensors"

# ── 3. VAE Flux ──────────────────────────────────────────────────────────────

echo ""
echo "=== [3/6] VAE Flux ==="

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" \
  "$MODELS/vae/ae.safetensors" \
  "$HF_TOKEN"

# ── 4. Flux Redux + SigCLIP Vision ───────────────────────────────────────────

echo ""
echo "=== [4/6] Flux Redux + SigCLIP Vision ==="

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-Redux-dev/resolve/main/flux1-redux-dev.safetensors" \
  "$MODELS/style_models/flux1-redux-dev.safetensors" \
  "$HF_TOKEN"

dl \
  "https://huggingface.co/Comfy-Org/sigclip_vision_384/resolve/main/sigclip_vision_patch14_384.safetensors" \
  "$MODELS/clip_vision/sigclip_vision_patch14_384.safetensors"

# ── 5. LTX-Video 2.3 — checkpoint + LoRAs + Upscaler ─────────────────────────

echo ""
echo "=== [5/6] LTX-Video 2.3 22B (~22 Go) + LoRAs + Upscaler ==="

dl \
  "https://huggingface.co/Lightricks/LTX-2.3-fp8/resolve/main/ltx-2.3-22b-dev-fp8.safetensors" \
  "$MODELS/checkpoints/ltx-2.3-22b-dev-fp8.safetensors"

dl \
  "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-22b-distilled-lora-384.safetensors" \
  "$MODELS/loras/ltx-2.3-22b-distilled-lora-384.safetensors"

dl \
  "https://huggingface.co/Lightricks/LTX-2.3/resolve/main/ltx-2.3-spatial-upscaler-x2-1.1.safetensors" \
  "$MODELS/latent_upscale_models/ltx-2.3-spatial-upscaler-x2-1.1.safetensors"

# ── 6. Gemma 3 12B — text encoder pour LTX-Video 2.3 ─────────────────────────

echo ""
echo "=== [6/6] Gemma 3 12B (text encoder + abliterated LoRA) ==="

dl \
  "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors" \
  "$MODELS/text_encoders/gemma_3_12B_it_fp4_mixed.safetensors"

dl \
  "https://huggingface.co/Comfy-Org/ltx-2/resolve/main/split_files/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors" \
  "$MODELS/loras/gemma-3-12b-it-abliterated_lora_rank64_bf16.safetensors"

# ── Résumé ────────────────────────────────────────────────────────────────────

echo ""
echo "=== Contenu du volume ==="
find "$MODELS" -type f | sort | while read -r f; do
  printf "  %-70s %s\n" "$f" "$(du -sh "$f" | cut -f1)"
done
echo ""
echo "Done."
