#!/usr/bin/env python3
"""
==============================================================================
Verda 3-Tier Benchmark Orchestrator
==============================================================================
Manages lifecycle, health checks, and live benchmark execution across:
  1. GPU Inference Node (antanom-gpu-vm)
  2. Victim Sandbox Node (victim-sandbox-vm)
  3. Attacker Agent Node (attacker-runner-vm)

Usage:
  python3 scripts/orchestrate_3tier.py up
  python3 scripts/orchestrate_3tier.py status
  python3 scripts/orchestrate_3tier.py run --tier easy
  python3 scripts/orchestrate_3tier.py reset
  python3 scripts/orchestrate_3tier.py stop
  python3 scripts/orchestrate_3tier.py start
  python3 scripts/orchestrate_3tier.py down [--wipe-all]
==============================================================================
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, List, Optional, Tuple

CLUSTER_NODES = {
    "gpu": {
        "hostname": "antanom-gpu-vm",
        "instance_type": "1A100.22V",
        "image": "24.04.cuda12.9.docker",
        "provision_script": "scripts/provision_gpu_node.sh",
        "description": "Antanom vLLM GPU Inference Node",
    },
    "victim": {
        "hostname": "victim-sandbox-vm",
        "instance_type": "CPU.4V.16G",
        "image": "24.04.cuda12.9.docker",
        "provision_script": "scripts/provision_victim_node.sh",
        "description": "Isolated CTF Target Sandbox Node",
    },
    "attacker": {
        "hostname": "attacker-runner-vm",
        "instance_type": "CPU.4V.16G",
        "image": "24.04.cuda12.9.docker",
        "provision_script": "scripts/provision_attacker_node.sh",
        "description": "OpenCode Autonomous Agent Node",
    }
}

CACHE_VOLUME_NAME = "antanom-cache-vol"
CACHE_VOLUME_SIZE = 200  # GB
LOCATION = "FIN-01"
DEFAULT_SSH_KEY_NAME = "google-compute-engine"


def find_ssh_key() -> str:
    """Detects available SSH private key for root access."""
    candidates = [
        Path.home() / ".ssh/google_compute_engine",
        Path.home() / ".ssh/id_rsa",
        Path.home() / ".ssh/id_ed25519",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(Path.home() / ".ssh/id_rsa")


def run_cmd(cmd: List[str], check: bool = True, capture_json: bool = False) -> Tuple[int, str]:
    """Helper to execute shell command."""
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)
        output = res.stdout.strip()
        if capture_json:
            try:
                return res.returncode, json.loads(output)
            except json.JSONDecodeError:
                pass
        return res.returncode, output
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stderr.strip() or e.stdout.strip()


def run_verda_json(cmd: List[str]) -> any:
    """Executes a verda CLI command in agent/json mode."""
    full_cmd = ["verda"] + cmd + ["--agent"]
    code, out = run_cmd(full_cmd, check=False)
    if code != 0:
        print(f"[!] Verda CLI error: {out}", file=sys.stderr)
        return None
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return None


def get_active_vms() -> Dict[str, dict]:
    """Fetches currently active VMs indexed by hostname."""
    vms = run_verda_json(["vm", "list"])
    if not isinstance(vms, list):
        return {}
    res = {}
    for vm in vms:
        hostname = vm.get("hostname")
        if hostname:
            res[hostname] = vm
    return res


def get_volumes() -> Dict[str, dict]:
    """Fetches volumes indexed by name."""
    vols = run_verda_json(["volume", "list"])
    if not isinstance(vols, list):
        return {}
    res = {}
    for vol in vols:
        name = vol.get("name")
        if name:
            res[name] = vol
    return res


def ssh_exec(ip: str, remote_cmd: str, stream: bool = False) -> Tuple[int, str]:
    """Executes a remote command on a VM via SSH."""
    key = find_ssh_key()
    cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-o", "ConnectTimeout=10",
        "-i", key,
        f"root@{ip}",
        remote_cmd
    ]
    if stream:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        full_output = []
        for line in iter(proc.stdout.readline, ""):
            sys.stdout.write(line)
            sys.stdout.flush()
            full_output.append(line)
        proc.wait()
        return proc.returncode, "".join(full_output)
    else:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode, res.stdout.strip() or res.stderr.strip()


def ssh_upload(ip: str, local_path: str, remote_path: str) -> bool:
    """Uploads a file via SCP."""
    key = find_ssh_key()
    cmd = [
        "scp",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        "-i", key,
        local_path,
        f"root@{ip}:{remote_path}"
    ]
    code, _ = run_cmd(cmd, check=False)
    return code == 0


def cmd_status(args):
    """Displays real-time status of all 3 cluster nodes."""
    print("\n==================== 3-TIER CLUSTER STATUS ====================")
    vms = get_active_vms()
    vols = get_volumes()

    print(f"Persistent Cache Volume ('{CACHE_VOLUME_NAME}'):")
    if CACHE_VOLUME_NAME in vols:
        v = vols[CACHE_VOLUME_NAME]
        print(f"  [✓] ID: {v.get('id')} | Size: {v.get('size')} GB | Status: {v.get('status')}")
    else:
        print("  [✗] Volume not created yet.")

    print("\nVirtual Machine Nodes:")
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        vm = vms.get(hostname)
        if vm:
            status = vm.get("status", "unknown")
            ip = vm.get("ip", "pending")
            itype = vm.get("instance_type", "")
            cost = vm.get("price_per_hour", 0.0)
            print(f"  ● {role.upper():<8} ({hostname}):")
            print(f"      Status: {status} | IP: {ip} | Type: {itype} | Cost: ${cost:.4f}/hr")

            # Quick health probe
            if status == "running" and ip and ip != "pending":
                if role == "gpu":
                    ready = check_vllm_health(ip)
                    print(f"      Health: {'[READY] vLLM responding on port 8000' if ready else '[STARTING] Waiting for vLLM container'}")
                elif role == "victim":
                    ready = check_http_health(f"http://{ip}:8080")
                    print(f"      Health: {'[READY] Tier 1 target responding on port 8080' if ready else '[STARTING] Target containers building'}")
                elif role == "attacker":
                    code, out = ssh_exec(ip, "opencode -v 2>/dev/null || echo 'not ready'")
                    print(f"      Health: [READY] OpenCode {out}" if code == 0 and "not ready" not in out else "      Health: [STARTING] OpenCode installing")
        else:
            print(f"  ○ {role.upper():<8} ({hostname}): NOT RUNNING")
    print("===============================================================\n")


def check_vllm_health(ip: str, port: int = 8000) -> bool:
    try:
        url = f"http://{ip}:{port}/v1/models"
        req = urllib.request.Request(url, headers={"Authorization": "Bearer c3fc1b8d4cc59e524cf789a828366924ede1db1acf2ea3e34cf264a7493afeec"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def check_http_health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            return resp.status in [200, 301, 302, 401, 403]
    except Exception:
        return False


def cmd_up(args):
    """Spins up and provisions all 3 cluster nodes."""
    print("\n[+] Deploying 3-Tier Isolated Cluster on Verda Cloud...")
    vms = get_active_vms()
    vols = get_volumes()

    # 1. Cache Volume
    cache_vol_id = None
    if CACHE_VOLUME_NAME in vols:
        cache_vol_id = vols[CACHE_VOLUME_NAME].get("id")
        print(f"[+] Found existing cache volume '{CACHE_VOLUME_NAME}' ({cache_vol_id})")
    else:
        print(f"[+] Creating persistent {CACHE_VOLUME_SIZE}GB NVMe cache volume '{CACHE_VOLUME_NAME}'...")
        vol_res = run_verda_json([
            "volume", "create",
            "--name", CACHE_VOLUME_NAME,
            "--size", str(CACHE_VOLUME_SIZE),
            "--type", "NVMe",
            "--location", LOCATION
        ])
        if vol_res and "id" in vol_res:
            cache_vol_id = vol_res["id"]
            print(f"[+] Created cache volume {cache_vol_id}")

    # 2. Spin up VMs if missing
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        if hostname in vms:
            print(f"[+] Node '{hostname}' ({role}) is already active.")
            continue

        print(f"[+] Launching {role.upper()} node: {hostname} ({conf['instance_type']})...")
        create_args = [
            "vm", "create",
            "--hostname", hostname,
            "--instance-type", conf["instance_type"],
            "--image", conf["image"],
            "--location", LOCATION,
            "--contract", "spot",
            "--ssh-key", DEFAULT_SSH_KEY_NAME
        ]
        if role == "gpu" and cache_vol_id:
            create_args += ["--volume", cache_vol_id]

        vm_res = run_verda_json(create_args)
        print(f"[+] Created {hostname}: {vm_res}")

    print("\n[+] Waiting for VMs to acquire public IPs and SSH availability...")
    time.sleep(15)
    vms = get_active_vms()

    # 3. Provision nodes via SSH
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        vm = vms.get(hostname)
        if not vm:
            continue
        ip = vm.get("ip")
        if not ip or ip == "pending":
            continue

        script_path = conf["provision_script"]
        if not os.path.exists(script_path):
            print(f"[!] Provision script {script_path} not found locally, skipping remote bootstrap.")
            continue

        print(f"\n[+] Provisioning {role.upper()} node ({ip}) with {script_path}...")
        remote_dest = f"/tmp/{os.path.basename(script_path)}"
        ssh_upload(ip, script_path, remote_dest)
        ssh_exec(ip, f"chmod +x {remote_dest} && nohup {remote_dest} > /tmp/provision.log 2>&1 &")

    print("\n[+] All 3 nodes launched and bootstrapping in background.")
    print("[+] Use 'python3 scripts/orchestrate_3tier.py status' to monitor readiness.")


def cmd_run(args):
    """Executes the benchmark from the Attacker VM against the Victim VM."""
    vms = get_active_vms()
    gpu_vm = vms.get(CLUSTER_NODES["gpu"]["hostname"])
    victim_vm = vms.get(CLUSTER_NODES["victim"]["hostname"])
    attacker_vm = vms.get(CLUSTER_NODES["attacker"]["hostname"])

    if not (gpu_vm and victim_vm and attacker_vm):
        print("[!] Error: All 3 nodes must be running to execute the benchmark.", file=sys.stderr)
        print("Run 'python3 scripts/orchestrate_3tier.py up' first.", file=sys.stderr)
        sys.exit(1)

    gpu_ip = gpu_vm.get("ip")
    victim_ip = victim_vm.get("ip")
    attacker_ip = attacker_vm.get("ip")

    print("\n=======================================================")
    print(f"Launching 3-Tier Isolated Benchmark Evaluation")
    print(f"Tier:            {args.tier}")
    print(f"Attacker Host:   {attacker_ip}")
    print(f"Victim Host:     {victim_ip}")
    print(f"Inference Host:  {gpu_ip}:8000")
    print("=======================================================\n")

    eval_cmd = (
        f"python3 /root/Serverless-Inference-Qwen3.8/ctf_challenges/scripts/run_ctf_eval.py "
        f"--tier {args.tier} "
        f"--target-host {victim_ip} "
        f"--vllm-ip {gpu_ip} "
        f"--vllm-port 8000 "
        f"--timeout {args.timeout}"
    )
    if args.thinking:
        eval_cmd += " --thinking"

    code, out = ssh_exec(attacker_ip, eval_cmd, stream=True)
    sys.exit(code)


def cmd_reset(args):
    """Resets CTF challenge environments on the Victim VM."""
    vms = get_active_vms()
    victim_vm = vms.get(CLUSTER_NODES["victim"]["hostname"])
    if not victim_vm or not victim_vm.get("ip"):
        print("[!] Victim VM is not active.")
        return

    victim_ip = victim_vm["ip"]
    print(f"[+] Resetting target CTF containers on Victim VM ({victim_ip})...")
    code, out = ssh_exec(victim_ip, "/usr/local/bin/reset_ctf_targets.sh", stream=True)
    if code == 0:
        print("[✓] Victim target sandbox successfully reset.")
    else:
        print(f"[!] Reset failed: {out}")


def cmd_stop(args):
    """Shuts down/hibernates VMs to halt compute costs."""
    print("[+] Halting compute billing: shutting down cluster VMs...")
    vms = get_active_vms()
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        vm = vms.get(hostname)
        if vm and vm.get("status") == "running":
            vm_id = vm.get("id")
            print(f"[+] Stopping {hostname} ({vm_id})...")
            run_verda_json(["vm", "shutdown", vm_id])
    print("[✓] All VMs stopped. Storage cache preserved.")


def cmd_start(args):
    """Starts previously stopped VMs."""
    print("[+] Starting cluster VMs...")
    vms = get_active_vms()
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        vm = vms.get(hostname)
        if vm and vm.get("status") in ["offline", "stopped"]:
            vm_id = vm.get("id")
            print(f"[+] Starting {hostname} ({vm_id})...")
            run_verda_json(["vm", "start", vm_id])
    print("[✓] Start signal issued. Check status in 15 seconds.")


def cmd_down(args):
    """Terminates cluster VMs. By default preserves persistent cache volume."""
    print("[+] Tearing down 3-Tier Cluster...")
    vms = get_active_vms()
    for role, conf in CLUSTER_NODES.items():
        hostname = conf["hostname"]
        vm = vms.get(hostname)
        if vm:
            vm_id = vm.get("id")
            print(f"[+] Deleting VM {hostname} ({vm_id})...")
            # NOTE: We do NOT pass --with-volumes so the persistent cache volume survives!
            run_verda_json(["vm", "delete", vm_id, "--yes"])

    if args.wipe_all:
        print(f"[!] --wipe-all specified: deleting persistent cache volume '{CACHE_VOLUME_NAME}'...")
        vols = get_volumes()
        if CACHE_VOLUME_NAME in vols:
            vol_id = vols[CACHE_VOLUME_NAME].get("id")
            run_verda_json(["volume", "delete", vol_id, "--yes"])
            print(f"[✓] Deleted volume {vol_id}")
    else:
        print(f"[✓] Persistent cache volume '{CACHE_VOLUME_NAME}' kept intact for zero-wait future runs.")


def main():
    parser = argparse.ArgumentParser(description="Verda 3-Tier Benchmark Orchestrator")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # status
    subparsers.add_parser("status", help="Show cluster node status and health checks")

    # up
    subparsers.add_parser("up", help="Spin up and provision all 3 cluster nodes")

    # run
    run_p = subparsers.add_parser("run", help="Run benchmark from Attacker against Victim")
    run_p.add_argument("--tier", choices=["easy", "medium", "advanced", "egress_firewall", "token_scope"], default="easy")
    run_p.add_argument("--timeout", type=int, default=1800)
    run_p.add_argument("--thinking", action="store_true", default=False)

    # reset
    subparsers.add_parser("reset", help="Reset CTF containers on Victim VM")

    # stop / start
    subparsers.add_parser("stop", help="Shut down VMs to halt compute costs")
    subparsers.add_parser("start", help="Start stopped VMs")

    # down
    down_p = subparsers.add_parser("down", help="Delete VMs")
    down_p.add_argument("--wipe-all", action="store_true", default=False, help="Also wipe persistent cache storage")

    args = parser.parse_args()

    commands = {
        "status": cmd_status,
        "up": cmd_up,
        "run": cmd_run,
        "reset": cmd_reset,
        "stop": cmd_stop,
        "start": cmd_start,
        "down": cmd_down,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
