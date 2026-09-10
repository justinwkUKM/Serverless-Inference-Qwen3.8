# Verda VM Deployment & Automated Idle Watchdog Operations

This document details the architecture, operational workflows, automated idle shutdown watchdog, and cost management for the dedicated **NVIDIA A100 SXM4 80GB** VM running `MaanVad3r/Antanom` on Verda Cloud.

---

## 1. System Overview & Architecture

Unlike the serverless container deployment (`verda_container`), this deployment runs on an on-demand dedicated cloud instance for predictable high-throughput inference and low time-to-first-token (TTFT).

```text
                               ┌─────────────────────────────────────────────────────────────┐
                               │                    Verda Dedicated VM                       │
                               │                    (artanom-a100-vm)                        │
                               │                                                             │
Incoming Inference Requests ──►│  [Port 8000] vLLM OpenAI-compatible API                     │
                               │     Model: MaanVad3r/Antanom (served as 'Antanom')          │
                               │     Engine: vLLM v0.26.0 (CUDA 12.9, FP8 KV Cache)          │
                               │     GPU: 1x NVIDIA A100-SXM4-80GB                           │
                               │                                                             │
                               │  [Systemd] idle-watchdog.service                            │
                               │     ├── Polls http://127.0.0.1:8000/metrics every 5s        │
                               │     ├── Tracks active inference & interactive SSH sessions   │
                               │     ├── Safeguards cold boot & 51GB checkpoint load         │
                               │     └── Idle timeout (10 mins)                              │
                               │            │                                                │
                               │            ▼                                                │
                               │     1. Calls Verda Cloud API (vm action shutdown)           │
                               │     2. Executes local OS poweroff                           │
                               └────────────┼────────────────────────────────────────────────┘
                                            │
                                            ▼
                              Verda Cloud Control Plane
                              Status transitions: running ──► offline
                              GPU billing halted ($1.79/hr -> $0.00/hr)
```

---

## 2. Infrastructure Specifications

| Component | Specification |
| :--- | :--- |
| **Instance ID** | `9a80c4e7-d072-4a13-8551-109878f45cc9` |
| **Hostname** | `antanom-a100-vm` |
| **Instance Type** | `1A100.22V` |
| **Location** | `FIN-01` |
| **GPU** | 1x NVIDIA A100-SXM4-80GB (80 GB VRAM) |
| **Compute** | 22 vCPUs, 120 GB RAM |
| **Storage** | 200 GB NVMe OS Volume (`antanom-a100-vm-os`) |
| **External IP** | `135.181.8.204` |
| **Public Inference Port** | `8000` (`http://135.181.8.204:8000/v1`) |
| **Base Image** | `ubuntu-24.04-cuda-12.8-open-docker` |

---

## 3. Serving Configuration (vLLM)

vLLM runs inside a persistent Docker container (`vllm/vllm-openai:v0.26.0-cu129-ubuntu2404`):

- **Model ID:** `MaanVad3r/Antanom` (Served model name: `Antanom`)
- **Weights Cache:** Bind-mounted to `/opt/hf-cache` on NVMe storage (persists across reboots).
- **Quantization / Memory:**
  - `tensor-parallel-size`: `1`
  - `kv-cache-dtype`: `fp8`
  - `gpu-memory-utilization`: `0.90` (~72.4 GB allocated to weights + KV cache)
  - `max-model-len`: `131072` (128K context window)
  - `enable-chunked-prefill`: Enabled (`max-num-batched-tokens: 16384`)
  - `enable-prefix-caching`: Enabled

---

## 4. Automated Idle Watchdog Daemon

Because dedicated GPU cloud instances continue billing if left on, the VM runs a custom systemd background service:

- **Service Unit:** `/etc/systemd/system/idle-watchdog.service`
- **Script:** `/usr/local/bin/idle_watchdog.py`
- **Idle Threshold:** **10 minutes (600 seconds)**
- **Poll Interval:** 5 seconds

### How It Works:
1. **Activity Detection via Prometheus Metrics:**
   - Every 5 seconds, queries `http://127.0.0.1:8000/metrics`.
   - Checks `vllm:num_requests_running` and `vllm:request_success_total`.
   - If requests are currently processing or completed request count increases, `last_activity` is reset to `now`.
2. **Interactive SSH Detection:**
   - Checks `who` command. If an administrator has an open interactive session, the timer remains reset so maintenance is never interrupted.
3. **Boot Safeguard:**
   - Loading 51 GB of weights from NVMe into GPU VRAM takes ~3.3 minutes. The watchdog detects if the metrics endpoint is not yet reachable and holds the idle timer at `0s` until the server reports healthy and online.
4. **Cloud-Integrated Shutdown:**
   - When 10 minutes of complete inactivity elapse, the daemon executes:
     ```bash
     HOME=/root /usr/bin/verda --agent vm action --id $INSTANCE_ID --action shutdown --yes
     ```
   - This notifies Verda Cloud's hypervisor to transition the VM to **`offline`** and stop GPU billing.
   - It then cleanly runs `/sbin/poweroff` to shut down the guest OS.

---

## 5. Operations & Quick-Reference Commands

### Starting the VM
To boot up the instance when needed:
```bash
verda vm start 9a80c4e7-d072-4a13-8551-109878f45cc9
```
*Note: Takes ~2.5–3 minutes to boot the OS, start Docker, and load the 51GB model into GPU memory.*

### Checking Instance Status
```bash
verda vm list
```

### Checking Watchdog Logs (Live)
```bash
ssh -i ~/.ssh/google_compute_engine root@135.181.8.204 "journalctl -u idle-watchdog -f"
```

### Testing Endpoint Health
```bash
curl http://135.181.8.204:8000/health
```

### Sending a Test Inference Request
```bash
curl -X POST http://135.181.8.204:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_VERDA_INFERENCE_KEY>" \
  -d '{
    "model": "Antanom",
    "messages": [{"role": "user", "content": "Ping test"}],
    "max_tokens": 16
  }'
```

---

## 6. Cost & Financial Optimization

| State | GPU Compute ($1.79/hr) | NVMe Storage Retention ($0.05/hr) | Total Cost / Day |
| :--- | :--- | :--- | :--- |
| **`offline` (Idle Watchdog Shutdown)** | **$0.00** | **$1.32 / day** ($40.00/mo) | **$1.32 / day** |
| **`running` (Left Active 24/7)** | **$42.96 / day** | **$1.32 / day** ($40.00/mo) | **$44.28 / day** ($1,346/mo) |

**Cost Savings:** By automatically shutting down after 10 minutes of inactivity, an intermittent 2-hour daily workload costs **~$4.90/day** instead of **$44.28/day**, saving over **90%** on cloud compute while keeping all model caches intact.
