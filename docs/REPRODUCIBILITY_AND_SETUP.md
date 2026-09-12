# Complete VM Specification & Rapid Recreation Guide

This guide documents the exact configuration, infrastructure parameters, and automated scripts required to spin up and provision a fresh **Dedicated A100 SXM4 80GB** VM for `MaanVad3r/Antanom` from scratch in case the current instance is deleted or terminated.

---

## 1. Quick Recreation (One-Click)

If you have terminated the VM and wish to redeploy it with identical settings:

### Step 1: Create the VM via Verda CLI
From your local machine (with `verda` CLI configured):

```bash
verda vm create \
  --kind gpu \
  --instance-type 1A100.22V \
  --location FIN-01 \
  --os ubuntu-24.04-cuda-12.8-open-docker \
  --os-volume-size 200 \
  --hostname antanom-a100-vm \
  --description "Antanom vLLM A100 80GB" \
  --ssh-key <YOUR_SSH_KEY_ID> \
  --wait
```

### Step 2: Provision the VM
Get the new IP address from `verda vm list`, then copy and run the automated provisioning script:

```bash
NEW_IP="<NEW_VM_IP>"

# Copy provisioning script to the new VM
scp -i ~/.ssh/google_compute_engine scripts/provision_vm.sh root@$NEW_IP:/root/provision_vm.sh

# Run provisioning
ssh -i ~/.ssh/google_compute_engine root@$NEW_IP "bash /root/provision_vm.sh"
```

The script automatically installs Verda CLI, configures API credentials, installs and starts the 15-minute idle watchdog daemon, pulls the vLLM container, and begins loading `MaanVad3r/Antanom`.

---

## 2. Infrastructure & Compute Specification

| Parameter | Value | Notes |
| :--- | :--- | :--- |
| **Provider** | Verda Cloud | Finland Data Center (`FIN-01`) |
| **Instance Type** | `1A100.22V` | 1x NVIDIA A100-SXM4-80GB (80GB HBM2e VRAM) |
| **vCPUs / RAM** | 22 vCPUs / 120 GB RAM | Provides ample headroom for model loading and tokenization |
| **OS Image** | `ubuntu-24.04-cuda-12.8-open-docker` | Ubuntu 24.04 LTS, NVIDIA Driver 580+, CUDA 13 / 12.8, Docker Pre-installed |
| **OS Volume** | 200 GB NVMe (`NVMe`) | Sized to hold base OS (15GB), vLLM Docker image (18GB), model weights (51GB), and KV caches |
| **Pricing** | \$1.79 / hr compute (when running), \$0.05 / hr storage (~$1.32/day) | Pay-as-you-go |
| **SSH Key** | `<YOUR_SSH_KEY_ID>` | Provisioned in Verda Cloud dashboard |

---

## 3. Serving Engine Configuration (vLLM)

### Docker Run Command
```bash
docker run -d \
  --name vllm \
  --restart always \
  --gpus all \
  --ipc=host \
  -p 8000:8000 \
  -v /opt/hf-cache:/root/.cache/huggingface \
  vllm/vllm-openai:v0.26.0-cu129-ubuntu2404 \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key <YOUR_VERDA_INFERENCE_KEY> \
  --model MaanVad3r/Antanom \
  --served-model-name Antanom \
  --tensor-parallel-size 1 \
  --max-model-len 131072 \
  --kv-cache-dtype fp8 \
  --gpu-memory-utilization 0.90 \
  --enable-prefix-caching \
  --max-num-batched-tokens 16384 \
  --enable-chunked-prefill \
  --reasoning-parser qwen3 \
  --default-chat-template-kwargs '{"enable_thinking":false}' \
  --enable-auto-tool-choice \
  --tool-call-parser qwen3_coder
```

### Parameter Rationale
- `--restart always`: Ensures the inference engine auto-starts whenever the VM boots.
- `-v /opt/hf-cache:/root/.cache/huggingface`: Preserves downloaded Hugging Face safetensors across container recreations and OS reboots.
- `--gpu-memory-utilization 0.90`: Allocates ~72.4 GB VRAM to vLLM (51GB for weights + ~21.4GB for FP8 KV cache and activation buffers).
- `--kv-cache-dtype fp8`: Doubles effective context capacity, supporting over 448,000 tokens in active KV cache.
- `--max-model-len 131072`: Enables full 128K context window for long-context analysis.
- `--enable-chunked-prefill` & `--enable-prefix-caching`: Minimizes prefill latency and maximizes prompt reuse efficiency across repeated system prompts.

---

## 4. Automated Idle Watchdog Configuration

### Systemd Unit File: `/etc/systemd/system/idle-watchdog.service`
```ini
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
```

### Key Watchdog Script Settings (`/usr/local/bin/idle_watchdog.py`)
- `IDLE_LIMIT = 900` (15 minutes)
- `POLL_INTERVAL = 5` (Checks metrics every 5 seconds)
- `METRICS_URL = "http://127.0.0.1:8000/metrics"`
- **Verda API Auth:** Reads credentials from `/root/.verda/credentials`.
- **Auto-Shutdown Action:** Calls `/usr/bin/verda --agent vm action --id <INSTANCE_ID> --action shutdown --yes`, then runs `/sbin/poweroff`.

---

## 5. Post-Setup Verification Checklist

After deploying a new VM, execute these verification checks:

1. **Verify GPU State:**
   ```bash
   nvidia-smi
   ```
   *Expected:* 1x NVIDIA A100-SXM4-80GB visible with `VLLM::EngineCore` allocating ~53–72 GB VRAM.

2. **Verify vLLM Health:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```
   *Expected:* HTTP 200 (empty body).

3. **Verify Watchdog Monitoring:**
   ```bash
   journalctl -u idle-watchdog -n 10 --no-pager
   ```
   *Expected:* `Idle watchdog started. Idle limit: 900s (15 min).`

4. **Verify Verda Cloud CLI from Inside VM:**
   ```bash
   HOME=/root /usr/bin/verda --agent vm list
   ```
   *Expected:* Valid JSON listing the running VM.

5. **Run Quick Test Inference:**
   ```bash
   ./scripts/test.sh
   ```
   *Expected:* Successful completion with streamed or JSON output from `Antanom`.
