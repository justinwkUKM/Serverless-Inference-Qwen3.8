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

# Pass the friendly environment names through to Terraform variables.
export TF_VAR_deployment_name="${DEPLOYMENT_NAME}"
export TF_VAR_model_id="${MODEL_ID}"

echo "== Verda Qwen3.8 deployment =="
echo "Deployment: ${DEPLOYMENT_NAME}"
echo "Model:      ${MODEL_ID}"

terraform init
terraform fmt -check
terraform validate
terraform plan -out=tfplan

echo
read -r -p "Apply this saved plan? [y/N] " response
if [[ "${response}" =~ ^[Yy]$ ]]; then
  terraform apply tfplan
else
  echo "Deployment cancelled; no infrastructure was changed."
fi
