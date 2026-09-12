#!/usr/bin/env python3
"""
CyberGym Real-Time Monitoring Dashboard
========================================
Reads `benchmark_state.json` and displays a live terminal status dashboard
showing task execution phases, resource gauges, and progress metrics.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path


def render_dashboard(state_path: Path):
    if not state_path.exists():
        print(f"[!] Waiting for state file: {state_path}...")
        return

    try:
        data = json.loads(state_path.read_text())
    except Exception:
        return

    iteration = data.get("iteration", 1)
    total = data.get("total_tasks", 10)
    completed = data.get("completed_count", 0)
    running = data.get("running_count", 0)
    pending = data.get("pending_count", 0)
    elapsed = data.get("elapsed_seconds", 0.0)
    metrics = data.get("host_metrics", {})
    disk_free = metrics.get("disk_free_gb", "N/A")
    ram_avail = metrics.get("ram_available_gb", "N/A")

    # Clear terminal
    print("\033[2J\033[H", end="")
    print("=" * 75)
    print(f"  CYBERGYM BENCHMARK REAL-TIME DASHBOARD (Iteration: {iteration})")
    print("=" * 75)
    print(f"  Progress:   [{completed}/{total} Tasks Completed]  "
          f"Running: {running}  |  Pending: {pending}  |  Elapsed: {round(elapsed/60, 1)}m")
    print(f"  Resources:  Disk Free: {disk_free} GB  |  RAM Available: {ram_avail} GB")
    print("-" * 75)
    print(f"  {'TASK ID':<22} {'STATUS':<12} {'PHASE':<18} {'ELAPSED':<10} {'DELIVERABLES'}")
    print("-" * 75)

    tasks = data.get("tasks", {})
    for tid, tinfo in tasks.items():
        st = tinfo.get("status", "PENDING")
        ph = tinfo.get("phase", "QUEUED")
        el = f"{tinfo.get('elapsed_seconds', 0.0)}s" if tinfo.get('elapsed_seconds') else "-"
        poc = "PoC:✓" if tinfo.get("has_poc") else "PoC:✗"
        patch = "Patch:✓" if tinfo.get("has_patch") else "Patch:✗"

        # Color coding
        color = "\033[0m"
        if st == "COMPLETED":
            color = "\033[92m" # Green
        elif st == "FAILED":
            color = "\033[91m" # Red
        elif st == "RUNNING":
            color = "\033[93m" # Yellow

        print(f"  {color}{tid:<22} {st:<12} {ph:<18} {el:<10} {poc} {patch}\033[0m")

    print("=" * 75)
    print("  [Auto-refreshing every 2s | Press Ctrl+C to exit]")


def main():
    parser = argparse.ArgumentParser(description="CyberGym Live Dashboard")
    parser.add_argument("--state-file", type=Path, default=None)
    parser.add_argument("--interval", type=int, default=2)
    args = parser.parse_args()

    state_path = args.state_file
    if state_path is None:
        for candidate in [
            Path("benchmarks/runs/iteration_2/benchmark_state.json"),
            Path("benchmarks/runs/cybergym_10/benchmark_state.json"),
        ]:
            if candidate.exists():
                state_path = candidate
                break
        if state_path is None:
            state_path = Path("benchmarks/runs/iteration_2/benchmark_state.json")

    while True:
        try:
            render_dashboard(state_path)
            time.sleep(args.interval)
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    main()
