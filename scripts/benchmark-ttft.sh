#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/env.sh"

usage() {
  echo "Usage: $0 --phase smoke|baseline|final --mode direct|proxy --execute"
  echo "Without --execute, the command prints the matrix without sending traffic."
}

phase=""
mode="direct"
execute="false"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --phase) phase="${2:-}"; shift 2 ;;
    --mode) mode="${2:-}"; shift 2 ;;
    --execute) execute="true"; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage >&2; exit 2 ;;
  esac
done

if [[ ! "${phase}" =~ ^(smoke|baseline|final)$ ]] || [[ ! "${mode}" =~ ^(direct|proxy)$ ]]; then
  usage >&2
  exit 2
fi
if [[ ! -f "${ENV_FILE}" ]]; then
  echo "Missing ${ENV_FILE}" >&2
  exit 1
fi

if [[ -f "${PROJECT_DIR}/.env" ]]; then
  set -a
  source "${PROJECT_DIR}/.env"
  set +a
fi
source "${ENV_FILE}"
cd "${PROJECT_DIR}"

case "${phase}" in
  smoke) runs=3; profiles=("50:1:unique" "1000:1:shared-prefix") ;;
  baseline) runs=20; profiles=(
    "50:1:unique" "50:4:unique" "50:8:unique"
    "1000:1:unique" "1000:4:unique" "1000:8:unique"
    "10000:1:unique" "10000:4:unique" "10000:8:unique"
    "50:1:shared-prefix" "1000:1:shared-prefix" "10000:1:shared-prefix"
  ) ;;
  final) runs=20; profiles=(
    "50:1:unique" "50:4:unique" "50:8:unique"
    "1000:1:unique" "1000:4:unique" "1000:8:unique"
    "10000:1:unique" "10000:4:unique" "10000:8:unique"
    "50:4:shared-prefix" "1000:4:shared-prefix" "10000:4:shared-prefix"
    "50:4:cache-miss"
  ) ;;
esac

echo "TTFT phase: ${phase}"
echo "Endpoint mode: ${mode}"
echo "Runs per cell: ${runs}"
echo "Traffic enabled: ${execute}"
for profile in "${profiles[@]}"; do
  IFS=: read -r words concurrency prompt_mode <<< "${profile}"
  command=(python3 tests/benchmark_ttft_matrix.py --mode "${mode}" --target-words "${words}" --concurrency "${concurrency}" --runs "${runs}" --prompt-mode "${prompt_mode}" --max-tokens 128)
  printf '  '
  printf '%q ' "${command[@]}"
  printf '\n'
  if [[ "${execute}" == "true" ]]; then
    "${command[@]}"
  fi
done

if [[ "${phase}" == "final" ]]; then
  command=(python3 tests/benchmark_ttft_matrix.py --mode "${mode}" --target-words 50 --concurrency 4 --runs 100 --prompt-mode unique --max-tokens 128)
  printf '  '
  printf '%q ' "${command[@]}"
  printf '\n'
  if [[ "${execute}" == "true" ]]; then
    "${command[@]}"
  fi
fi
