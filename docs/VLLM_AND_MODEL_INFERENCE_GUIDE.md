# vLLM Engine & Antanom Model Inference Guide

This document provides a comprehensive reference for the serving stack, model architecture, vLLM configuration, and OpenAI-compatible inference API for **`MaanVad3r/Antanom`** deployed on the dedicated NVIDIA A100-SXM4-80GB GPU instance.

---

## 1. Model Architecture & Specifications

| Parameter | Specification | Details |
| :--- | :--- | :--- |
| **Model Repository** | [`MaanVad3r/Antanom`](https://huggingface.co/MaanVad3r/Antanom) | Hugging Face Hub |
| **Served Model Name** | `Antanom` | Alias expected in `"model"` parameter of OpenAI requests |
| **Model Type** | Decoder-only LLM (Qwen3.5 / GDN hybrid architecture) | Optimized for code analysis, penetration testing & defensive reasoning |
| **Parameter Scale** | ~27B–32B parameters | Weights stored as 2 safetensors shards (~50.96 GiB total on disk) |
| **Precision** | `bfloat16` weights | FP8 KV cache for memory-efficient multi-turn context |
| **Native Context Length** | Up to **131,072 tokens (128K)** | Enabled via `--max-model-len 131072` |
| **Default Chat Template** | OpenAI ChatML format | Supports system, user, assistant, and tool call roles |
| **Reasoning Parser** | `qwen3` | Reasoning / thinking tokens parsing |
| **Tool Calling Parser** | `qwen3_coder` | Native function calling and structured tool outputs |

---

## 2. vLLM Serving Engine Configuration

The serving layer runs on **vLLM `v0.26.0`** (`vllm/vllm-openai:v0.26.0-cu129-ubuntu2404`) with CUDA 12.9.

### Full Launch Command

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

### Deep Dive: Engine Flags Explained

- `--gpu-memory-utilization 0.90`:
  Allocates **90% of the 80 GB VRAM (~72.4 GiB)**. 
  - Model weights: **51.1 GiB**
  - CUDA Graph capture: **2.38 GiB**
  - KV Cache pool: **14.75 GiB** (holds **448,557 tokens** simultaneously)
- `--kv-cache-dtype fp8`:
  Stores KV cache in 8-bit floating point (`torch.float8_e4m3fn`). This halves KV cache memory usage compared to BF16 without perceptible degradation in generation quality, allowing 3.42x concurrency at 128K context.
- `--enable-prefix-caching`:
  Caches common prompt prefixes across requests (such as system prompts, coding rubrics, and penetration testing instructions). If multiple users or scripts query with identical initial prompts, time-to-first-token drops to near-zero.
- `--enable-chunked-prefill`:
  Splits massive input prompts into chunks of `16384` tokens. This prevents prefill requests from stalling ongoing token generation for other concurrent requests.
- `--tensor-parallel-size 1`:
  Direct single-GPU execution without inter-GPU communication overhead.
- `--default-chat-template-kwargs '{"enable_thinking":false}'`:
  Configures Qwen3 generation templates to directly generate responses without internal chain-of-thought XML wrappers when clean outputs are desired.
- `--enable-auto-tool-choice` & `--tool-call-parser qwen3_coder`:
  Enables OpenAI-compatible tool use (`tools` and `tool_choice`), automatically parsing function calls into JSON schemas.

---

## 3. Inference API Endpoints & Request Specifications

The server exposes standard **OpenAI-compatible HTTP endpoints** at `http://135.181.8.204:8000/v1`:

### Authentication Header
Every inference request must include:
```http
Authorization: Bearer <YOUR_VERDA_INFERENCE_KEY>
```

### 1. Chat Completions (`POST /v1/chat/completions`)

#### Basic Non-Streaming Request
```bash
curl -s -X POST http://135.181.8.204:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_VERDA_INFERENCE_KEY>" \
  -d '{
    "model": "Antanom",
    "messages": [
      {"role": "system", "content": "You are a senior application security engineer."},
      {"role": "user", "content": "Explain how to mitigate SQL injection vulnerabilities with prepared statements."}
    ],
    "temperature": 0.7,
    "top_p": 0.95,
    "max_tokens": 1024
  }' | jq .
```

#### Streaming Request (Server-Sent Events)
```bash
curl -N -X POST http://135.181.8.204:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_VERDA_INFERENCE_KEY>" \
  -d '{
    "model": "Antanom",
    "messages": [
      {"role": "user", "content": "Write a Python script to verify TLS certificate expiry."}
    ],
    "stream": true,
    "max_tokens": 512
  }'
```

#### Tool / Function Calling Request
```bash
curl -s -X POST http://135.181.8.204:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <YOUR_VERDA_INFERENCE_KEY>" \
  -d '{
    "model": "Antanom",
    "messages": [
      {"role": "user", "content": "What is the security score for example.com?"}
    ],
    "tools": [
      {
        "type": "function",
        "function": {
          "name": "check_domain_security",
          "description": "Analyze domain DNS, headers, and SSL configuration",
          "parameters": {
            "type": "object",
            "properties": {
              "domain": {"type": "string"}
            },
            "required": ["domain"]
          }
        }
      }
    ],
    "tool_choice": "auto"
  }' | jq .
```

### 2. Available Utility Endpoints

| Endpoint | Method | Purpose | Response |
| :--- | :--- | :--- | :--- |
| `/health` | `GET` | Health check probe | HTTP 200 OK |
| `/v1/models` | `GET` | Lists available models | `{"data": [{"id": "Antanom", ...}]}` |
| `/metrics` | `GET` | Prometheus telemetry | Active request counts, latency metrics, KV cache usage |

---

## 4. Client SDK Integrations

### Python (`openai` SDK >= 1.0)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://135.181.8.204:8000/v1",
    api_key="<YOUR_VERDA_INFERENCE_KEY>",
)

response = client.chat.completions.create(
    model="Antanom",
    messages=[
        {"role": "system", "content": "You are a cybersecurity research assistant."},
        {"role": "user", "content": "Provide a checklist for hardening Linux SSH servers."}
    ],
    temperature=0.7,
    max_tokens=2048,
)

print(response.choices[0].message.content)
```

### Node.js (`openai` npm package)
```javascript
import OpenAI from "openai";

const openai = new OpenAI({
  baseURL: "http://135.181.8.204:8000/v1",
  apiKey: "<YOUR_VERDA_INFERENCE_KEY>",
});

const response = await openai.chat.completions.create({
  model: "Antanom",
  messages: [{ role: "user", content: "Analyze potential CSRF vectors in cookie-based auth." }],
  max_tokens: 1024,
});

console.log(response.choices[0].message.content);
```

### Quicksilver Chat Web App Integration (`.env`)
To point the local Quicksilver chat frontend to this dedicated VM:
```ini
VERDA_ENDPOINT=http://135.181.8.204:8000
VERDA_INFERENCE_KEY=<YOUR_VERDA_INFERENCE_KEY>
VERDA_MODEL=Antanom
```

---

## 5. Inference Benchmarking & Performance Baseline

Empirical benchmarks run on this A100-SXM4 instance across 10 deep offensive cybersecurity test suites (4096 max tokens) demonstrate:

- **Time to First Token (TTFT):** **0.808 seconds** (average)
- **Token Generation Speed:** **28.08 tokens/second** (sustained single-stream decode)
- **Average Completion Length:** **3,198 tokens** per benchmark response
- **Completion Success Rate:** **100%** (`finish_reason: stop` across all 10 tests)
- **Prefix Caching Efficiency:** Repeated system prompts drop initial TTFT to **< 0.15 seconds**.

Detailed benchmark figures and test prompts can be inspected in [`benchmarks/runs/offensive_10_benchmark_report.md`](../benchmarks/runs/offensive_10_benchmark_report.md).
