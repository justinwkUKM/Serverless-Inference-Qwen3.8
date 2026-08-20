#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/env.sh"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}. Copy scripts/env.example to scripts/env.sh and add your credentials." >&2
  exit 1
fi

cd "${PROJECT_DIR}"
source "${ENV_FILE}"
export TF_VAR_deployment_name="${DEPLOYMENT_NAME}"
export TF_VAR_model_id="${MODEL_ID}"
terraform plan -destroy

echo
read -r -p "Destroy the Qwen deployment and persistent storage? [y/N] " response
if [[ "${response}" =~ ^[Yy]$ ]]; then
  terraform destroy
else
  echo "Destroy cancelled."
fi
