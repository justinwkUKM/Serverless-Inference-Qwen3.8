#!/usr/bin/env bash
# ==============================================================================
# CyberGym 10-Task Host Environment Setup Script
# Configures kernel ASLR, installs OpenCode agent CLI, and configures Docker
# isolated networking on the Verda A100 GPU instance.
# ==============================================================================

set -euo pipefail

echo "======================================================================"
echo " Starting CyberGym Host Environment Setup"
echo "======================================================================"

# 1. Adjust ASLR entropy for AddressSanitizer / MemorySanitizer compatibility
echo "[1/4] Configuring Linux ASLR entropy (vm.mmap_rnd_bits=28)..."
sudo sysctl -w vm.mmap_rnd_bits=28
if ! grep -q "vm.mmap_rnd_bits=28" /etc/sysctl.conf 2>/dev/null; then
    echo "vm.mmap_rnd_bits=28" | sudo tee -a /etc/sysctl.conf
fi
echo "      ASLR configured: $(sysctl vm.mmap_rnd_bits)"

# 2. Check Docker daemon status
echo "[2/4] Verifying Docker daemon..."
if ! command -v docker &>/dev/null; then
    echo "ERROR: docker is not installed. Please install docker first." >&2
    exit 1
fi
docker info >/dev/null 2>&1 || {
    echo "ERROR: Docker daemon is not running or current user lacks permission." >&2
    exit 1
}
echo "      Docker is operational."

# 3. Install OpenCode CLI if not present
echo "[3/4] Checking OpenCode CLI..."
if ! command -v opencode &>/dev/null; then
    echo "      OpenCode not found. Installing via official installer..."
    curl -fsSL https://opencode.ai/install | bash
    export PATH="$HOME/.opencode/bin:$HOME/.local/bin:$PATH"
fi
echo "      OpenCode CLI available: $(command -v opencode)"

# 4. Create isolated Docker bridge network for task sandboxes
echo "[4/4] Configuring isolated Docker network (cybergym_net)..."
NETWORK_NAME="cybergym_net"
SUBNET="172.28.0.0/16"

if ! docker network inspect "$NETWORK_NAME" >/dev/null 2>&1; then
    docker network create --subnet="$SUBNET" "$NETWORK_NAME"
    echo "      Created network $NETWORK_NAME on $SUBNET"
else
    echo "      Network $NETWORK_NAME already exists."
fi

# Apply firewall rule: Allow traffic from sandbox network to host/loopback/VPC,
# but prevent arbitrary external internet egress (prevents reward-hacking).
echo "      Applying network egress isolation rules..."
sudo iptables -I DOCKER-USER -s "$SUBNET" -j DROP || true
sudo iptables -I DOCKER-USER -s "$SUBNET" -d 127.0.0.0/8 -j ACCEPT || true
sudo iptables -I DOCKER-USER -s "$SUBNET" -d 10.0.0.0/8 -j ACCEPT || true
sudo iptables -I DOCKER-USER -s "$SUBNET" -d 172.16.0.0/12 -j ACCEPT || true
sudo iptables -I DOCKER-USER -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT || true

echo "======================================================================"
echo " CyberGym Host Setup Complete!"
echo " Next step: Run python3 scripts/run_cybergym_10.py"
echo "======================================================================"
