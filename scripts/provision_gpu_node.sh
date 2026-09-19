#!/usr/bin/env bash
# ==============================================================================
# Verda 3-Tier Benchmark: GPU Inference Node Provisioning Script
# Role: Serves MaanVad3r/Antanom via vLLM on Port 8000 with Persistent Caching
# ==============================================================================
set -euo pipefail

MODEL_ID="${MODEL_ID:-MaanVad3r/Antanom}"
SERVED_MODEL_NAME="${SERVED_MODEL_NAME:-Antanom}"
CACHE_DIR="${CACHE_DIR:-/opt/hf-cache}"
PORT="${PORT:-8000}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-65536}"
GPU_MEM_UTIL="${GPU_MEM_UTIL:-0.90}"
VLLM_IMAGE="${VLLM_IMAGE:-vllm/vllm-openai:v0.26.0-cu129-ubuntu2404}"

echo "======================================================================"
echo ">>> [GPU Node] Initializing Antanom vLLM Inference Service"
echo ">>> Model: ${MODEL_ID} (Served as: ${SERVED_MODEL_NAME})"
echo ">>> Cache Directory: ${CACHE_DIR}"
echo "======================================================================"

# 1. Create or mount cache directory
mkdir -p "${CACHE_DIR}"

# 2. Check if vLLM container is already running
if docker ps --format '{{.Names}}' | grep -q "^vllm$"; then
  echo ">>> [GPU Node] vLLM container is already running."
else
  # Remove stopped container if exists
  docker rm -f vllm 2>/dev/null || true

  echo ">>> [GPU Node] Launching vLLM container..."
  docker run -d \
    --name vllm \
    --restart always \
    --gpus all \
    --ipc=host \
    -p "${PORT}:8000" \
    -v "${CACHE_DIR}:/root/.cache/huggingface" \
    -e HF_HUB_ENABLE_HF_TRANSFER="1" \
    "${VLLM_IMAGE}" \
    --host 0.0.0.0 \
    --port 8000 \
    --model "${MODEL_ID}" \
    --served-model-name "${SERVED_MODEL_NAME}" \
    --tensor-parallel-size 1 \
    --max-model-len "${MAX_MODEL_LEN}" \
    --gpu-memory-utilization "${GPU_MEM_UTIL}" \
    --kv-cache-dtype fp8 \
    --enable-prefix-caching \
    --trust-remote-code
fi

echo ">>> [GPU Node] Provisioning complete. vLLM is starting on port ${PORT}."
