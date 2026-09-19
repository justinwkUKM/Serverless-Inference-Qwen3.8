# 3-Tier Isolated Benchmark Architecture on Verda Cloud

This document outlines the architecture, setup, and orchestration workflow for running autonomous cybersecurity agent benchmarks (such as Antanom with OpenCode) in a **100% isolated 3-tier cloud environment**.

---

## 1. Threat Model & Architecture Overview

To ensure the benchmark is scientifically sound, reproducible, and impervious to environment contamination or unintentional cheating, the workload is distributed across three separate virtual machines in Verda's `FIN-01` datacenter:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Verda Cloud (FIN-01 DC)                            │
│                                                                             │
│  ┌───────────────────────┐                    ┌──────────────────────────┐  │
│  │   GPU Inference Node  │◄─── OpenAI API ────┤   Attacker Agent Node    │  │
│  │  (1A100.22V Spot VM)  │    (Port 8000)     │   (CPU.4V.16G Spot VM)   │  │
│  │  • vLLM v0.26 / v0.6  │                    │  • OpenCode CLI          │  │
│  │  • MaanVad3r/Antanom  │                    │  • Evaluation Harness    │  │
│  │  • Persistent NVMe Vol│                    │  • Security Tooling      │  │
│  └───────────────────────┘                    └────────────┬─────────────┘  │
│                                                            │                │
│                                                     Target HTTP/SSH         │
│                                                     (Ports 8080/8443/etc.)  │
│                                                            │                │
│                                               ┌────────────▼─────────────┐  │
│                                               │    Victim Sandbox Node   │  │
│                                               │   (CPU.4V.16G Spot VM)   │  │
│                                               │  • Dockerized CTF targets│  │
│                                               │  • Zero agent access     │  │
│                                               │  • Clean state reset     │  │
│                                               └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Fairness & Isolation Guarantees
1. **Zero Host Introspection**: The OpenCode agent runs on the **Attacker VM** and has no access to the Docker daemon or filesystem of the **Victim VM**. It cannot inspect container environment variables or local disk volumes to bypass exploitation.
2. **Zero Resource Starvation**: Heavy fuzzing or scanning commands run by the agent consume CPU on the Attacker VM, never degrading target responsiveness or model inference speed.
3. **Low Inter-VM Latency**: All instances reside in the same datacenter (`FIN-01`), achieving `< 1 ms` roundtrip times without public internet variability.

---

## 2. Infrastructure & Cost Profile

| Node Role | Verda Instance Type | Specs | Spot Price / hr | Recommended Lifecycle |
| :--- | :--- | :--- | :--- | :--- |
| **GPU Inference** | `1A100.22V` | 22 vCPU, 1x A100 (80GB), 120GB RAM | **$0.8675** | Shutdown/hibernate when idle |
| **Attacker Agent** | `CPU.4V.16G` | 4 vCPU, 16GB RAM | **$0.0192** | Terminate after benchmark run |
| **Victim Sandbox** | `CPU.4V.16G` | 4 vCPU, 16GB RAM | **$0.0192** | Terminate after benchmark run |
| **Golden Cache** | Persistent NVMe | 200 GB | **$0.0548** (~$40/mo) | Keep detached between runs to preserve model weights |
| **Total Cluster Cost** | &mdash; | &mdash; | **~$0.96 / hr** | **< $1.00 for a full multi-tier benchmark run** |

---

## 3. Fast-Boot Golden Cache Storage

To prevent 20–30 minute delays downloading the vLLM Docker image and the 16 GB `MaanVad3r/Antanom` Hugging Face model weights on every spin-up:
* A persistent 200 GB NVMe volume (`antanom-cache-vol`) is attached to `/opt/hf-cache` on the GPU node.
* When terminating VMs with `orchestrate_3tier.py down`, the volume remains in your account detached.
* Subsequent boots mount the volume instantly, enabling **sub-45-second ready times**.

---

## 4. Orchestration CLI Commands

The cluster is managed via `scripts/orchestrate_3tier.py`:

### Check Cluster Status
```bash
python3 scripts/orchestrate_3tier.py status
```

### Spin Up the 3-Tier Cluster
```bash
python3 scripts/orchestrate_3tier.py up
```

### Run a Benchmark Evaluation
```bash
# Tier 1: Easy (Port 8080)
python3 scripts/orchestrate_3tier.py run --tier easy

# Tier 2: Medium (Port 8443)
python3 scripts/orchestrate_3tier.py run --tier medium

# Tier 3: Advanced (Port 8888)
python3 scripts/orchestrate_3tier.py run --tier advanced
```

### Reset Target Sandbox to Clean State
```bash
python3 scripts/orchestrate_3tier.py reset
```

### Pause Cluster (Halt Compute Billing)
```bash
python3 scripts/orchestrate_3tier.py stop
```

### Resume Cluster
```bash
python3 scripts/orchestrate_3tier.py start
```

### Teardown Cluster
```bash
# Tear down VMs but keep golden storage cache for next time:
python3 scripts/orchestrate_3tier.py down

# Full wipe (including volume):
python3 scripts/orchestrate_3tier.py down --wipe-all
```
