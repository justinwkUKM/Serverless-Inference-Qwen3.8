#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_DIR}"

ENDPOINT="${VERDA_ENDPOINT:-$(terraform output -raw endpoint_base_url)}"
: "${VERDA_INFERENCE_KEY:?Set VERDA_INFERENCE_KEY or source scripts/env.sh}"

curl --fail --silent --show-error \
  -H "Authorization: Bearer ${VERDA_INFERENCE_KEY}" \
  "${ENDPOINT%/}/health"
echo
