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
mkdir -p "$MODELS/ipadapter"
mkdir -p "$MODELS/loras"
mkdir -p "$MODELS/pulid"
mkdir -p "$MODELS/insightface/models"

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

# ── 5. PuLID Flux — cohérence identité personnages ───────────────────────────
# PuLID préserve l'identité faciale d'un personnage dans différentes scènes
# Custom node requis dans le Docker : cubiq/PuLID_ComfyUI

echo ""
echo "=== [5/7] PuLID Flux v0.9.1 (~1.1 Go) ==="

dl \
  "https://huggingface.co/guozinan/PuLID/resolve/main/pulid_flux_v0.9.1.safetensors" \
  "$MODELS/pulid/pulid_flux_v0.9.1.safetensors"

echo ""
echo "=== [6/7] EVA-CLIP (requis par PuLID, ~856 Mo) ==="

dl \
  "https://huggingface.co/QuanSun/EVA-CLIP/resolve/main/EVA02_CLIP_L_336_psz14_s6B.pt" \
  "$MODELS/text_encoders/EVA02_CLIP_L_336_psz14_s6B.pt"

echo ""
echo "=== [6b/7] InsightFace antelopev2 (requis par PuLID, ~430 Mo) ==="

ANTELOPE_ZIP="$MODELS/insightface/models/antelopev2.zip"
ANTELOPE_DIR="$MODELS/insightface/models/antelopev2"

if [[ -d "$ANTELOPE_DIR" ]] && [[ "$(ls -A "$ANTELOPE_DIR" 2>/dev/null)" ]]; then
  echo "  [SKIP] antelopev2 — déjà présent"
else
  echo "  [DL]   antelopev2.zip"
  wget -q --show-progress \
    "https://github.com/deepinsight/insightface/releases/download/v0.7/antelopev2.zip" \
    -O "$ANTELOPE_ZIP"
  unzip -q "$ANTELOPE_ZIP" -d "$MODELS/insightface/models/"
  rm "$ANTELOPE_ZIP"
  echo "  [OK]   antelopev2 — $(du -sh "$ANTELOPE_DIR" | cut -f1)"
fi

# ── 7. LTX-Video 13B — animation image-to-video ─────────────────────────────
# Modèle Lightricks LTX-Video 13B 0.9.8 dev (~28.5 Go)
# Custom node requis : https://github.com/Lightricks/ComfyUI-LTXVideo

echo ""
echo "=== [7/7] LTX-Video 13B 0.9.8 dev (~28.5 Go) ==="

dl \
  "https://huggingface.co/Lightricks/LTX-Video/resolve/main/ltxv-13b-0.9.8-dev.safetensors" \
  "$MODELS/checkpoints/ltxv-13b-0.9.8-dev.safetensors"

# ── Résumé ────────────────────────────────────────────────────────────────────

echo ""
echo "=== Contenu du volume ==="
find "$MODELS" -type f | sort | while read -r f; do
  printf "  %-70s %s\n" "$f" "$(du -sh "$f" | cut -f1)"
done
echo ""
echo "Done."
