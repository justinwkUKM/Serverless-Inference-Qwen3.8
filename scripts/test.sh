#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

ENDPOINT="${VERDA_ENDPOINT:-$(terraform output -raw endpoint_base_url)}"
: "${VERDA_INFERENCE_KEY:?Set VERDA_INFERENCE_KEY or source scripts/env.sh}"

curl --fail --silent --show-error \
  -X POST \
  "${ENDPOINT%/}/v1/chat/completions" \
  -H "Authorization: Bearer ${VERDA_INFERENCE_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3.8-27b",
    "messages": [
      {"role": "system", "content": "You are a concise cybersecurity analyst."},
      {"role": "user", "content": "Explain Kerberoasting and provide three defensive controls."}
    ],
    "temperature": 0.7,
    "top_p": 0.8,
    "max_tokens": 512,
    "stream": false
  }'
echo
