#!/usr/bin/env bash
# ==============================================================================
# Verda 3-Tier Benchmark: Attacker Agent Node Provisioning Script
# Role: Runs OpenCode agent and evaluation harness against isolated victim node
# ==============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/justinwkUKM/Serverless-Inference-Qwen3.8.git}"
TARGET_DIR="${TARGET_DIR:-/root/Serverless-Inference-Qwen3.8}"

echo "======================================================================"
echo ">>> [Attacker Node] Provisioning Autonomous Security Agent Environment"
echo "======================================================================"

# 1. Update OS and install essential penetration testing tools
apt-get update -qq
apt-get install -y -qq \
  curl \
  git \
  jq \
  nmap \
  netcat-openbsd \
  python3 \
  python3-pip \
  python3-requests \
  python3-venv \
  dnsutils \
  whois \
  traceroute \
  hydra \
  sqlmap

# 2. Install OpenCode CLI if not present
if ! command -v opencode &>/dev/null; then
  echo ">>> [Attacker Node] Installing OpenCode CLI..."
  curl -fsSL https://opencode.ai/install | bash
  ln -sf /root/.opencode/bin/opencode /usr/local/bin/opencode || true
fi

echo ">>> [Attacker Node] OpenCode version: $(opencode -v 2>/dev/null || true)"

# 3. Clone or update repository
if [ -d "${TARGET_DIR}/.git" ]; then
  echo ">>> [Attacker Node] Updating repository..."
  git -C "${TARGET_DIR}" pull --rebase || true
else
  echo ">>> [Attacker Node] Cloning repository..."
  git clone "${REPO_URL}" "${TARGET_DIR}"
fi

echo "======================================================================"
echo ">>> [Attacker Node] Agent environment ready!"
echo ">>> Evaluation script located at: ${TARGET_DIR}/ctf_challenges/scripts/run_ctf_eval.py"
echo "======================================================================"
