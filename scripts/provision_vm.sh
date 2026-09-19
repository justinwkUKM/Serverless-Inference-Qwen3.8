#!/usr/bin/env bash
# ==============================================================================
# Verda A100 Dedicated VM Provisioning Script
# Sets up Docker, vLLM (Antanom), Verda CLI, and Automated Idle Watchdog
# ==============================================================================
set -euo pipefail

: "${VERDA_CLIENT_ID:?Set VERDA_CLIENT_ID before running this script}"
: "${VERDA_CLIENT_SECRET:?Set VERDA_CLIENT_SECRET before running this script}"
: "${VERDA_INFERENCE_KEY:?Set VERDA_INFERENCE_KEY before running this script}"

echo "===> [1/6] Preparing Hugging Face cache directory on NVMe storage..."
mkdir -p /opt/hf-cache

echo "===> [2/6] Installing Verda CLI (v1.8.2)..."
curl -sLO https://github.com/verda-cloud/verda-cli/releases/download/v1.8.2/verda_1.8.2_linux_amd64.deb
dpkg -i verda_1.8.2_linux_amd64.deb
rm -f verda_1.8.2_linux_amd64.deb

echo "===> [3/6] Configuring Verda credentials..."
mkdir -p /root/.verda
cat << EOF > /root/.verda/credentials
[default]
verda_base_url            = https://api.verda.com/v1
verda_client_id           = ${VERDA_CLIENT_ID}
verda_client_secret       = ${VERDA_CLIENT_SECRET}
EOF
chmod 600 /root/.verda/credentials

echo "===> [4/6] Installing Idle Watchdog Daemon..."
cat << 'EOF' > /usr/local/bin/idle_watchdog.py
#!/usr/bin/env python3
import time
import subprocess
import urllib.request
import re
import sys
import os
import json

IDLE_LIMIT = 900   # 15 minutes in seconds
POLL_INTERVAL = 5  # Check every 5 seconds for fast detection
METRICS_URL = "http://127.0.0.1:8000/metrics"

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def get_ssh_session_count():
    try:
        output = subprocess.check_output(["who"], universal_newlines=True)
        return len([line for line in output.strip().splitlines() if line.strip()])
    except Exception:
        return 0

def get_vllm_metrics():
    try:
        req = urllib.request.Request(METRICS_URL, headers={"User-Agent": "IdleWatchdog/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            body = response.read().decode("utf-8", errors="ignore")
        
        running_match = re.findall(r"^vllm:num_requests_running\{.*?\}\s+([0-9.]+)", body, re.MULTILINE)
        running = sum(float(x) for x in running_match) if running_match else 0.0

        success_match = re.findall(r"^vllm:request_success_total\{.*?\}\s+([0-9.]+)", body, re.MULTILINE)
        completed = sum(float(x) for x in success_match) if success_match else 0.0

        return running, completed, True
    except Exception:
        return 0.0, 0.0, False

def get_instance_id():
    env_id = os.environ.get("VERDA_INSTANCE_ID")
    if env_id:
        return env_id
    try:
        env = os.environ.copy()
        env["HOME"] = "/root"
        res = subprocess.check_output(["/usr/bin/verda", "--agent", "vm", "list"], universal_newlines=True, timeout=10, env=env)
        data = json.loads(res)
        if isinstance(data, list) and len(data) > 0:
            return data[0].get("id")
    except Exception:
        pass
    return None

def cloud_shutdown(instance_id):
    try:
        log(f"Calling Verda Cloud API to shutdown VM {instance_id}...")
        env = os.environ.copy()
        env["HOME"] = "/root"
        res = subprocess.run(
            ["/usr/bin/verda", "--agent", "vm", "action", "--id", instance_id, "--action", "shutdown", "--yes"],
            capture_output=True,
            text=True,
            timeout=30,
            env=env
        )
        log(f"Verda Cloud API result: {res.stdout.strip()} (err: {res.stderr.strip()})")
    except Exception as e:
        log(f"Verda Cloud API call error: {e}")

def main():
    log(f"Idle watchdog started. Idle limit: {IDLE_LIMIT}s (15 min). Poll interval: {POLL_INTERVAL}s.")
    last_activity = time.time()
    last_completed = None
    last_running_state = False
    last_idle_log = 0

    while True:
        time.sleep(POLL_INTERVAL)
        now = time.time()

        # 1. Check SSH sessions
        ssh_count = get_ssh_session_count()
        if ssh_count > 0:
            last_activity = now
            if now - last_idle_log >= 60:
                log(f"Active SSH session detected ({ssh_count} active). Resetting idle timer.")
                last_idle_log = now
            continue

        # 2. Check vLLM metrics
        running, completed, ok = get_vllm_metrics()
        if not ok:
            # Keep idle timer reset during model weight loading
            last_activity = now
            if now - last_idle_log >= 60:
                log("vLLM server starting up / metrics not ready yet. Keeping idle timer reset.")
                last_idle_log = now
            continue

        if last_completed is None:
            last_completed = completed
            last_activity = now
            log(f"vLLM engine is ONLINE (cumulative completed: {completed:.0f}). Starting idle monitoring ({IDLE_LIMIT}s limit).")
            continue

        # Check if requests are active
        if running > 0:
            last_activity = now
            if not last_running_state:
                log(f"Inference detected ({running:.0f} request(s) active). Resetting idle timer.")
                last_running_state = True
            continue
        else:
            last_running_state = False

        # Check if new completed requests were logged
        if completed > last_completed:
            delta = completed - last_completed
            last_activity = now
            last_completed = completed
            log(f"Inference completed (+{delta:.0f} request(s), total={completed:.0f}). Resetting idle timer.")
            continue

        last_completed = completed

        # System is completely idle
        idle_duration = int(now - last_activity)

        if now - last_idle_log >= 60:
            log(f"Idle: no inference and no SSH sessions for {idle_duration}s / {IDLE_LIMIT}s.")
            last_idle_log = now

        # Trigger shutdown when threshold is met
        if idle_duration >= IDLE_LIMIT:
            log(f"IDLE TIMEOUT REACHED ({idle_duration}s >= {IDLE_LIMIT}s). Initiating cloud shutdown & poweroff...")
            sys.stdout.flush()
            sys.stderr.flush()

            instance_id = get_instance_id()
            if instance_id:
                cloud_shutdown(instance_id)

            subprocess.run(["/sbin/poweroff"])
            return

if __name__ == "__main__":
    main()
EOF
chmod +x /usr/local/bin/idle_watchdog.py

cat << 'EOF' > /etc/systemd/system/idle-watchdog.service
[Unit]
Description=vLLM 15-Minute Idle Shutdown Watchdog
After=docker.service network.target

[Service]
Type=simple
Environment="HOME=/root"
ExecStart=/usr/bin/python3 -u /usr/local/bin/idle_watchdog.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable idle-watchdog.service
systemctl restart idle-watchdog.service

echo "===> [5/6] Pulling and launching vLLM Docker container..."
docker rm -f vllm || true

docker run -d \
  --name vllm \
  --restart always \
  --gpus all \
  --ipc=host \
  -p 8000:8000 \
  -v /opt/hf-cache:/root/.cache/huggingface \
  -e HF_TOKEN="${HF_TOKEN:-}" \
  -e HUGGING_FACE_HUB_TOKEN="${HF_TOKEN:-}" \
  vllm/vllm-openai:v0.26.0-cu129-ubuntu2404 \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "${VERDA_INFERENCE_KEY}" \
  --model MaanVad3r/Antanom \
  --served-model-name Antanom \
  --tensor-parallel-size 1 \
  --max-model-len 131072 \
  --max-num-seqs 256 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching \
  --max-num-batched-tokens 16384 \
  --enable-chunked-prefill \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking":false}' \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder

echo "===> [6/6] VM provisioning complete! vLLM is downloading/loading Antanom model."
