#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Script de setup complet du network volume RunPod
# Usage : HF_TOKEN=hf_xxx bash setup_models.sh
#
# Lancer depuis un pod RunPod avec le volume Visiobook attaché à /workspace
# =============================================================================

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "Erreur : HF_TOKEN non défini."
  echo "Usage : HF_TOKEN=hf_xxx bash setup_models.sh"
  exit 1
fi

if ! df -h /workspace &>/dev/null; then
  echo "Erreur : /workspace n'est pas monté."
  exit 1
fi

MODELS="/workspace/models"

# ── Création de la structure de dossiers ──────────────────────────────────────

mkdir -p "$MODELS/diffusion_models"
mkdir -p "$MODELS/text_encoders"
mkdir -p "$MODELS/vae"
mkdir -p "$MODELS/checkpoints"
mkdir -p "$MODELS/clip_vision"
mkdir -p "$MODELS/ipadapter"
mkdir -p "$MODELS/loras"

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
# Nécessite d'accepter la licence sur : https://huggingface.co/black-forest-labs/FLUX.1-dev

echo "=== [1/5] Flux.1-dev fp16 (~23 Go) ==="

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/flux1-dev.safetensors" \
  "$MODELS/diffusion_models/flux1_dev_fp16.safetensors" \
  "$HF_TOKEN"

# ── 2. Text encoders Flux ────────────────────────────────────────────────────

echo ""
echo "=== [2/5] Text encoders Flux ==="

dl \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp16.safetensors" \
  "$MODELS/text_encoders/t5xxl_fp16.safetensors"

dl \
  "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
  "$MODELS/text_encoders/clip_l.safetensors"

# ── 3. VAE Flux ──────────────────────────────────────────────────────────────

echo ""
echo "=== [3/5] VAE Flux ==="

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-dev/resolve/main/ae.safetensors" \
  "$MODELS/vae/ae.safetensors" \
  "$HF_TOKEN"

# ── 4. Flux Redux (cohérence visuelle personnages entre scènes) ───────────────
# Nativement supporté par ComfyUI — pas de custom node requis

echo ""
echo "=== [4/5] Flux Redux + SigCLIP Vision ==="

mkdir -p "$MODELS/style_models"

dl \
  "https://huggingface.co/black-forest-labs/FLUX.1-Redux-dev/resolve/main/flux1-redux-dev.safetensors" \
  "$MODELS/style_models/flux1-redux-dev.safetensors" \
  "$HF_TOKEN"

dl \
  "https://huggingface.co/Comfy-Org/sigclip_vision_384/resolve/main/sigclip_vision_patch14_384.safetensors" \
  "$MODELS/clip_vision/sigclip_vision_patch14_384.safetensors"

# ── 5. Wan 2.1 I2V — génération vidéo ────────────────────────────────────────
# Modèle lourd (31 Go) — endpoint A100 80GB séparé
# Source : Comfy-Org/Wan_2.1_ComfyUI_repackaged (format ComfyUI natif)

echo ""
echo "=== [5/5] Wan 2.1 I2V 480p 14B (~31 Go) ==="

WAN_BASE="https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files"

dl \
  "$WAN_BASE/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors" \
  "$MODELS/diffusion_models/wan2.1_i2v_480p_14B_fp16.safetensors"

dl \
  "$WAN_BASE/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors" \
  "$MODELS/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors"

dl \
  "$WAN_BASE/vae/wan_2.1_vae.safetensors" \
  "$MODELS/vae/wan_2.1_vae.safetensors"

# ── Résumé ────────────────────────────────────────────────────────────────────

echo ""
echo "=== Contenu du volume ==="
find "$MODELS" -type f | sort | while read -r f; do
  printf "  %-70s %s\n" "$f" "$(du -sh "$f" | cut -f1)"
done
echo ""
echo "Done."
