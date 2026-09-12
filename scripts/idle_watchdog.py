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
            return data[0].get("id", "9a80c4e7-d072-4a13-8551-109878f45cc9")
    except Exception:
        pass
    return "9a80c4e7-d072-4a13-8551-109878f45cc9"

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
            # While vLLM is starting or reloading, do not count as idle
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

        # Log heartbeat every 60s so countdown is visible
        if now - last_idle_log >= 60:
            log(f"Idle: no inference and no SSH sessions for {idle_duration}s / {IDLE_LIMIT}s.")
            last_idle_log = now

        # Trigger shutdown when threshold is met
        if idle_duration >= IDLE_LIMIT:
            log(f"IDLE TIMEOUT REACHED ({idle_duration}s >= {IDLE_LIMIT}s). Initiating cloud shutdown & poweroff...")
            sys.stdout.flush()
            sys.stderr.flush()

            # Trigger Verda Cloud Shutdown first
            instance_id = get_instance_id()
            cloud_shutdown(instance_id)

            # Trigger local OS poweroff
            subprocess.run(["/sbin/poweroff"])
            return

if __name__ == "__main__":
    main()
