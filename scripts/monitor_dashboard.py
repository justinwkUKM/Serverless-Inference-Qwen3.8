#!/usr/bin/env python3
"""
CyberGym Real-Time Monitoring Dashboard (v4.0 - Enterprise Edition)
===================================================================
Interactive live terminal dashboard for monitoring CyberGym benchmark runs
locally or remotely via SSH across sliding window workers.

Features:
  - Real-time task execution tracking (Phases, Elapsed time, PoC/Patch).
  - Remote VM streaming via SSH (with auto-discovery of active iterations).
  - Live progress bar, ETA estimation, and host resource telemetry (RAM, Disk, GPU VRAM).
  - Scalable view designed for large task sets (e.g. Iteration 6 with 50 tasks).
  - One-shot (--once) or continuous live dashboard mode.
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple, Any

# ANSI colors
CLR_RESET = "\033[0m"
CLR_BOLD = "\033[1m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_BLUE = "\033[94m"
CLR_CYAN = "\033[96m"
CLR_RED = "\033[91m"
CLR_MAGENTA = "\033[95m"
CLR_GRAY = "\033[90m"
CLR_BG_DARK = "\033[40m"


def format_duration(seconds: float) -> str:
    """Formats seconds into human-readable duration (e.g., 2m 14s or 1h 05m)."""
    if seconds < 0:
        return "0s"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    rem_seconds = seconds % 60
    if minutes < 60:
        return f"{minutes}m {rem_seconds:02d}s"
    hours = minutes // 60
    rem_minutes = minutes % 60
    return f"{hours}h {rem_minutes:02d}m"


def find_ssh_key() -> Optional[str]:
    """Finds default SSH identity key if available."""
    candidates = [
        Path.home() / ".ssh/google_compute_engine",
        Path.home() / ".ssh/id_rsa",
        Path.home() / ".ssh/id_ed25519",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def fetch_remote_state(host: str, ssh_key: Optional[str] = None) -> Tuple[Optional[Dict], str]:
    """Fetches benchmark state JSON and host telemetry from remote VM over SSH."""
    key_opt = f"-i {ssh_key} " if ssh_key else ""
    remote_cmd = (
        "bash -c '"
        "LATEST=$(ls -td /root/cybergym_benchmark/benchmarks/runs/iteration_* 2>/dev/null | head -1);"
        "if [ -n \"$LATEST\" ] && [ -f \"$LATEST/benchmark_state.json\" ]; then "
        "  cat \"$LATEST/benchmark_state.json\"; "
        "elif [ -f /root/cybergym_benchmark/benchmarks/runs/cybergym_10/benchmark_state.json ]; then "
        "  cat /root/cybergym_benchmark/benchmarks/runs/cybergym_10/benchmark_state.json; "
        "else "
        "  echo \"{}\"; "
        "fi; "
        "echo \"===GPU===\"; "
        "nvidia-smi --query-gpu=memory.total,memory.used,utilization.gpu --format=csv,noheader,nounits 2>/dev/null || echo \"N/A\""
        "'"
    )
    cmd = f"ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 {key_opt}{host} \"{remote_cmd}\""
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return None, f"SSH error ({res.returncode}): {res.stderr.strip()}"
        
        parts = res.stdout.split("===GPU===")
        state_json = parts[0].strip()
        gpu_info = parts[1].strip() if len(parts) > 1 else ""

        if not state_json or state_json == "{}":
            return None, "No active benchmark_state.json found on remote VM."

        data = json.loads(state_json)
        if gpu_info and gpu_info != "N/A":
            try:
                gparts = [x.strip() for x in gpu_info.split(",")]
                if len(gparts) >= 2:
                    data.setdefault("host_metrics", {})
                    data["host_metrics"]["gpu_vram_total_mb"] = gparts[0]
                    data["host_metrics"]["gpu_vram_used_mb"] = gparts[1]
                    data["host_metrics"]["gpu_util_pct"] = gparts[2] if len(gparts) > 2 else "0"
            except Exception:
                pass
        return data, ""
    except subprocess.TimeoutExpired:
        return None, "SSH connection timed out."
    except Exception as e:
        return None, str(e)


def find_latest_state_file() -> Optional[Path]:
    """Discovers the most recent local benchmark state file."""
    repo_root = Path(__file__).resolve().parent.parent
    runs_dir = repo_root / "benchmarks/runs"
    
    if runs_dir.exists():
        state_files = sorted(
            runs_dir.glob("*/benchmark_state.json"),
            key=lambda p: p.stat().st_mtime if p.exists() else 0,
            reverse=True,
        )
        if state_files:
            return state_files[0]
            
    fallback = repo_root / "benchmarks/runs/iteration_6/benchmark_state.json"
    return fallback if fallback.exists() else None


def render_dashboard(data: Dict, source_label: str, show_all: bool = False):
    """Renders the formatted dashboard view."""
    iteration = data.get("iteration", "?")
    total = data.get("total_tasks", 0)
    completed = data.get("completed_count", 0)
    running = data.get("running_count", 0)
    pending = data.get("pending_count", 0)
    elapsed_total = data.get("elapsed_seconds", 0.0)
    metrics = data.get("host_metrics", {})
    disk_free = metrics.get("disk_free_gb", "N/A")
    ram_avail = metrics.get("ram_available_gb", "N/A")
    
    gpu_total = metrics.get("gpu_vram_total_mb")
    gpu_used = metrics.get("gpu_vram_used_mb")
    gpu_str = ""
    if gpu_total and gpu_used:
        try:
            used_gb = float(gpu_used) / 1024.0
            tot_gb = float(gpu_total) / 1024.0
            gpu_str = f"  |  GPU VRAM: {CLR_BOLD}{used_gb:.1f}/{tot_gb:.0f} GB{CLR_RESET}"
        except Exception:
            pass

    # ETA Calculation
    eta_str = "Calculating..."
    if completed > 0 and elapsed_total > 0:
        avg_sec_per_task = elapsed_total / completed
        remaining_tasks = total - completed
        est_sec = avg_sec_per_task * (remaining_tasks / 2.0)  # concurrency 2 sliding window
        eta_str = f"~{format_duration(est_sec)}"
    elif total > 0:
        eta_str = f"Estimating (~{total} tasks)..."

    # Screen dimensions
    term_width = shutil.get_terminal_size((90, 24)).columns
    banner_width = max(80, min(term_width, 100))

    # Header
    out = []
    out.append("\033[2J\033[H")  # Clear screen and return cursor to top-left
    out.append(f"{CLR_CYAN}{'=' * banner_width}{CLR_RESET}")
    out.append(f"{CLR_BOLD}  CYBERGYM BENCHMARK MONITORING DASHBOARD (Iteration: {iteration}){CLR_RESET}")
    out.append(f"{CLR_CYAN}{'=' * banner_width}{CLR_RESET}")

    # Progress bar
    bar_width = min(35, banner_width - 50)
    filled = int(bar_width * (completed / total)) if total > 0 else 0
    bar = f"{CLR_GREEN}{'#' * filled}{CLR_GRAY}{'-' * (bar_width - filled)}{CLR_RESET}"
    pct = (completed / total * 100) if total > 0 else 0.0

    out.append(f"  Progress:  [{bar}] {completed}/{total} ({pct:.1f}%)  |  ETA: {CLR_YELLOW}{eta_str}{CLR_RESET}")
    out.append(f"  Status:    {CLR_GREEN}Completed: {completed}{CLR_RESET}  |  "
               f"{CLR_YELLOW}Running: {running}{CLR_RESET}  |  "
               f"{CLR_GRAY}Pending: {pending}{CLR_RESET}  |  "
               f"Elapsed: {CLR_BOLD}{format_duration(elapsed_total)}{CLR_RESET}")
    out.append(f"  Telemetry: Disk Free: {CLR_BOLD}{disk_free} GB{CLR_RESET}  |  "
               f"RAM Available: {CLR_BOLD}{ram_avail} GB{CLR_RESET}{gpu_str}")
    out.append(f"{CLR_GRAY}{'-' * banner_width}{CLR_RESET}")
    out.append(f"  {'TASK ID':<16} {'STATUS':<11} {'PHASE':<17} {'RUNTIME':<10} {'DELIVERABLES':<14} {'INFO'}")
    out.append(f"{CLR_GRAY}{'-' * banner_width}{CLR_RESET}")

    tasks = data.get("tasks", {})
    now = datetime.datetime.now()

    # Sort tasks: RUNNING first, then COMPLETED/FAILED, then PENDING
    def task_sort_key(item):
        tinfo = item[1]
        st = tinfo.get("status", "PENDING")
        if st == "RUNNING":
            return (0, tinfo.get("started_at", ""))
        elif st in ("COMPLETED", "PASSED"):
            return (1, tinfo.get("completed_at", ""))
        elif st == "FAILED":
            return (2, tinfo.get("completed_at", ""))
        return (3, item[0])

    sorted_tasks = sorted(tasks.items(), key=task_sort_key)
    
    # If not showing all, show active + last 6 completed
    displayed_tasks = []
    if show_all:
        displayed_tasks = sorted_tasks
    else:
        active = [t for t in sorted_tasks if t[1].get("status") == "RUNNING"]
        finished = [t for t in sorted_tasks if t[1].get("status") in ("COMPLETED", "PASSED", "FAILED")]
        # Keep last 8 completed tasks
        recent_finished = finished[-8:] if len(finished) > 8 else finished
        displayed_tasks = active + recent_finished

    for tid, tinfo in displayed_tasks:
        st = tinfo.get("status", "PENDING")
        ph = tinfo.get("phase", "QUEUED")
        started_at_str = tinfo.get("started_at")
        early_exit = tinfo.get("early_exit", False)
        timed_out = tinfo.get("timed_out", False)

        # Calculate live elapsed time
        elapsed_display = "-"
        if tinfo.get("elapsed_seconds") and tinfo.get("elapsed_seconds") > 0:
            elapsed_display = format_duration(tinfo["elapsed_seconds"])
        elif started_at_str:
            try:
                st_time = datetime.datetime.fromisoformat(started_at_str)
                live_sec = (now - st_time).total_seconds()
                if live_sec > 0:
                    elapsed_display = f"~{format_duration(live_sec)}"
            except Exception:
                pass

        poc = f"{CLR_GREEN}PoC:✓{CLR_RESET}" if tinfo.get("has_poc") else f"{CLR_GRAY}PoC:✗{CLR_RESET}"
        patch = f"{CLR_GREEN}Patch:✓{CLR_RESET}" if tinfo.get("has_patch") else f"{CLR_GRAY}Patch:✗{CLR_RESET}"
        artifacts = f"{poc} {patch}"

        # Badges and details
        details = []
        if early_exit:
            details.append(f"{CLR_MAGENTA}[★ Early Exit]{CLR_RESET}")
        elif timed_out:
            details.append(f"{CLR_RED}[3h Timeout]{CLR_RESET}")
        elif st == "RUNNING" and ph == "AGENT_EXECUTION":
            details.append(f"{CLR_YELLOW}[Agent Active]{CLR_RESET}")
        elif ph == "PULL_JIT":
            details.append(f"{CLR_CYAN}[Pulling Image]{CLR_RESET}")

        desc = tinfo.get("desc", "")
        if desc and len(details) < 2:
            details.append(f"{CLR_GRAY}({desc[:30]}){CLR_RESET}")

        details_str = " ".join(details)

        # Status colors
        if st in ("COMPLETED", "PASSED"):
            st_color = CLR_GREEN
        elif st == "FAILED":
            st_color = CLR_RED
        elif st == "RUNNING":
            st_color = CLR_YELLOW
        else:
            st_color = CLR_GRAY

        out.append(f"  {tid:<16} {st_color}{st:<11}{CLR_RESET} {ph:<17} {elapsed_display:<10} {artifacts:<25} {details_str}")

    if not show_all and len(sorted_tasks) > len(displayed_tasks):
        hidden_count = len(sorted_tasks) - len(displayed_tasks)
        out.append(f"  {CLR_GRAY}... ({hidden_count} older completed or queued tasks hidden. Use --all to list entire set) ...{CLR_RESET}")

    out.append(f"{CLR_CYAN}{'=' * banner_width}{CLR_RESET}")
    out.append(f"  {CLR_GRAY}Source: {source_label} | Auto-refreshing every 2s | Press Ctrl+C to exit{CLR_RESET}")

    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="CyberGym Real-Time Monitoring Dashboard v4.0")
    parser.add_argument("--remote", "-r", nargs="?", const="root@65.109.75.62", default=None,
                        help="Remote SSH host to stream live metrics from (default: root@65.109.75.62)")
    parser.add_argument("--key", "-k", default=None, help="Path to SSH private key (default: auto-detected)")
    parser.add_argument("--state-file", "-f", type=Path, default=None, help="Local path to benchmark_state.json")
    parser.add_argument("--interval", "-i", type=int, default=2, help="Refresh interval in seconds (default: 2)")
    parser.add_argument("--once", action="store_true", help="Print dashboard once and exit immediately")
    parser.add_argument("--all", "-a", action="store_true", help="Show all tasks instead of active + recent")
    args = parser.parse_args()

    ssh_key = args.key or find_ssh_key()
    remote_host = args.remote

    # If no local state file is provided and no local one exists, default to remote VM
    if not args.state_file and not remote_host:
        local_candidate = find_latest_state_file()
        if not local_candidate or not local_candidate.exists():
            remote_host = "root@65.109.75.62"

    while True:
        try:
            if remote_host:
                data, err = fetch_remote_state(remote_host, ssh_key)
                if not data:
                    print(f"{CLR_YELLOW}[!] {err}{CLR_RESET}")
                else:
                    render_dashboard(data, f"Remote ({remote_host})", show_all=args.all)
            else:
                state_path = args.state_file or find_latest_state_file()
                if not state_path or not state_path.exists():
                    print(f"{CLR_YELLOW}[!] Waiting for state file... (Pass --remote to monitor remote VM){CLR_RESET}")
                else:
                    try:
                        data = json.loads(state_path.read_text())
                        render_dashboard(data, str(state_path), show_all=args.all)
                    except Exception as e:
                        print(f"{CLR_RED}[!] Error reading {state_path}: {e}{CLR_RESET}")

            if args.once:
                break
            time.sleep(args.interval)

        except KeyboardInterrupt:
            print(f"\n{CLR_RESET}Exiting dashboard.")
            break


if __name__ == "__main__":
    main()
