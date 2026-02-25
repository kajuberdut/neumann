#!/bin/bash
set -e

echo "Starting llama-server..."
echo "Model: $MODEL_FILE"
echo "Offloading Layers: ${N_GPU_LAYERS:-40}"
echo "Threads: ${THREADS:-14}"

exec /app/llama-server \
  --model "$MODEL_FILE" \
  --host 0.0.0.0 \
  --port 8080 \
  --n-gpu-layers "${N_GPU_LAYERS:-40}" \
  --threads "${THREADS:-14}" \
  --ctx-size "${CTX_SIZE:-32000}" \
  --flash-attn "${FLASH_ATTN:-on}" \
  --cache-type-k "${CACHE_TYPE_K:-f16}" \
  --cache-type-v "${CACHE_TYPE_V:-f16}" \
  --temp "${TEMP:-1.0}" \
  --top-p "${TOP_P:-0.95}" \
  --min-p "${MIN_P:-0.01}" \
  --top-k "${TOP_K:-40}" \
  --seed "${SEED:-3407}"