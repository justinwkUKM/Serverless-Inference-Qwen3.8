#!/usr/bin/env bash
# ==============================================================================
# Verda 3-Tier Benchmark: Victim Sandbox Node Provisioning Script
# Role: Hosts isolated CTF challenge targets inside Docker containers
# ==============================================================================
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/justinwkUKM/Serverless-Inference-Qwen3.8.git}"
TARGET_DIR="${TARGET_DIR:-/root/Serverless-Inference-Qwen3.8}"

echo "======================================================================"
echo ">>> [Victim Node] Provisioning Isolated Target Environments"
echo ">>> Repository: ${REPO_URL}"
echo "======================================================================"

# 1. Ensure git & docker compose are present
apt-get update -qq && apt-get install -y -qq git curl docker-compose-v2

# 2. Clone or update repository
if [ -d "${TARGET_DIR}/.git" ]; then
  echo ">>> [Victim Node] Updating existing repository..."
  git -C "${TARGET_DIR}" pull --rebase || true
else
  echo ">>> [Victim Node] Cloning repository..."
  git clone "${REPO_URL}" "${TARGET_DIR}"
fi

# 3. Build & start all CTF target environments
CHALLENGES_DIR="${TARGET_DIR}/ctf_challenges"

echo ">>> [Victim Node] Starting Tier 1 (Port 8080)..."
docker compose -f "${CHALLENGES_DIR}/tier1_easy/docker-compose.yml" up -d --build

echo ">>> [Victim Node] Starting Tier 2 (Port 8443)..."
docker compose -f "${CHALLENGES_DIR}/tier2_medium/docker-compose.yml" up -d --build

echo ">>> [Victim Node] Starting Tier 3 (Port 8888)..."
docker compose -f "${CHALLENGES_DIR}/tier3_advanced/docker-compose.yml" up -d --build

if [ -f "${CHALLENGES_DIR}/challenge_egress_firewall/docker-compose.yml" ]; then
  echo ">>> [Victim Node] Starting Egress Firewall Challenge (Port 8085)..."
  docker compose -f "${CHALLENGES_DIR}/challenge_egress_firewall/docker-compose.yml" up -d --build || true
fi

if [ -f "${CHALLENGES_DIR}/challenge_token_scope/docker-compose.yml" ]; then
  echo ">>> [Victim Node] Starting Token Scope Challenge (Port 8086)..."
  docker compose -f "${CHALLENGES_DIR}/challenge_token_scope/docker-compose.yml" up -d --build || true
fi

# 4. Install target reset script
cat << 'RESETEOF' > /usr/local/bin/reset_ctf_targets.sh
#!/usr/bin/env bash
set -e
DIR="/root/Serverless-Inference-Qwen3.8/ctf_challenges"
echo ">>> Resetting all challenge containers..."
for compose in $(find "$DIR" -name "docker-compose.yml"); do
  echo "Restarting $(dirname "$compose")..."
  docker compose -f "$compose" down -v || true
  docker compose -f "$compose" up -d --build
done
echo ">>> All challenge targets reset to clean state."
RESETEOF
chmod +x /usr/local/bin/reset_ctf_targets.sh

echo "======================================================================"
echo ">>> [Victim Node] Targets successfully deployed!"
echo ">>> Tier 1: Port 8080 | Tier 2: Port 8443 | Tier 3: Port 8888"
echo ">>> Reset tool installed at: /usr/local/bin/reset_ctf_targets.sh"
echo "======================================================================"
