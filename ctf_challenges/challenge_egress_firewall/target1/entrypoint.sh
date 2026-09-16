#!/usr/bin/env bash
set -e

# Configure strict egress filtering rules
# 1. Allow loopback
iptables -A OUTPUT -o lo -j ACCEPT

# 2. Allow established/related incoming sessions (responses to incoming requests)
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# 3. Allow internal communications to Target 2 subnet (172.28.0.0/24)
iptables -A OUTPUT -d 172.28.0.0/24 -j ACCEPT

# 4. DROP all other outbound traffic (blocks reverse shells to external networks / internet)
iptables -A OUTPUT -j DROP

# Ensure results directory is writable by appuser
mkdir -p /app/static/results
chmod 777 /app/static/results

# Run Flask application as unprivileged appuser
exec su - appuser -c "python3 /app/app.py"
