# Quicksilver

Private, OpenAI-compatible inference on Verda Serverless with Qwen3.8, vLLM,
streaming Markdown, performance telemetry, and optional Tavily web grounding.

Quicksilver combines reproducible Terraform infrastructure with a lightweight
local chat console. Secrets remain in the server process: the browser never
receives the Verda inference key, infrastructure credentials, or Tavily key.

## Highlights

- Qwen3.8 27B FP8 served through vLLM's OpenAI-compatible API
- Streaming Markdown chat with automatic scrolling and a responsive dark UI
- Client-observed TTFT, total latency, token usage, and decode throughput
- Manual health checks plus comparable warm and cold-test controls
- Optional Tavily search with linked sources and prompt-injection boundaries
- Server-side credential proxy with uncompressed SSE for immediate token flush
- Terraform-managed Verda Serverless deployment with scale-to-zero
- Dependency-free application server using Node.js built-ins

## Architecture

```text
Browser
  │  prompts and streamed SSE (no provider credentials)
  ▼
Quicksilver server · localhost:4173
  ├── optional Tavily Search
  └── authenticated Verda inference proxy
          ▼
      Verda Serverless
          ▼
      vLLM + Qwen3.8 27B FP8
```

## Deployment profile

| Setting | Value |
|---|---|
| Model | `unsloth/Qwen3.8-27B-NVFP4` |
| Runtime | `vllm/vllm-openai:v0.26.0-cu129-ubuntu2404` |
| Compute | 1× RTX PRO 6000 On-Demand, 96 GB |
| Context | 65,536 tokens |
| KV cache | FP8 |
| Prefix caching | Enabled |
| Batched-token budget | 16,384 |
| Replica range | 0–1 |
| Scale-down delay | 300 seconds |

The image uses a versioned tag because Verda does not accept moving tags such
as `latest`. The RTX PRO 6000 On-Demand configuration was listed at $2.079/GPU-hour when
selected; actual capacity and pricing depend on Verda's current compute market.

## Prerequisites

- Node.js 20 or newer
- Terraform 1.x
- Verda Cloud API credentials
- A Verda inference API key
- A Tavily key only if Web Search is required

## Local setup

```bash
git clone https://github.com/justinwkUKM/Serverless-Inference-Qwen3.8.git
cd Serverless-Inference-Qwen3.8

cp scripts/env.example scripts/env.sh
cp .env.example .env
chmod 600 scripts/env.sh .env
```

Configure `scripts/env.sh` for Terraform and command-line tools:

```bash
export VERDA_CLIENT_ID="PASTE_YOUR_CLIENT_ID"
export VERDA_CLIENT_SECRET="PASTE_YOUR_CLIENT_SECRET"
export VERDA_INFERENCE_KEY="PASTE_YOUR_INFERENCE_KEY"
export VERDA_ENDPOINT="https://your-verda-endpoint.example"
```

Configure `.env` for the local application:

```bash
VERDA_ENDPOINT=https://your-verda-endpoint.example
TAVILY_API_KEY=PASTE_YOUR_TAVILY_API_KEY
```

`VERDA_INFERENCE_KEY` is read from the process environment first and falls
back to the ignored `scripts/env.sh`. `TAVILY_API_KEY` and `VERDA_ENDPOINT`
can be supplied through the process environment or ignored `.env` file.

Start the console:

```bash
npm start
```

Open <http://127.0.0.1:4173>.

## Deploying to Verda

Review the compute identifier and other defaults in `variables.tf`, then run:

```bash
source scripts/env.sh
./scripts/deploy.sh
```

The deployment script initializes Terraform, validates the configuration,
creates a saved plan, and asks before applying billable infrastructure.

After deployment:

```bash
export VERDA_ENDPOINT="$(terraform output -raw endpoint_base_url)"
./scripts/health.sh
./scripts/test.sh
```

The first request after scale-to-zero can include GPU scheduling, image pull,
model loading, compilation, CUDA graph capture, and vLLM warm-up. On-Demand
capacity avoids Spot eviction but may still take time to allocate and initialize.

To remove the deployment and persistent cache:

```bash
./scripts/destroy.sh
```

## Web Search

Select **Web** in the composer to search Tavily before inference. The server:

1. sends the latest user query to Tavily Basic Search;
2. keeps up to five ranked source excerpts;
3. injects them as untrusted reference material;
4. instructs the model to cite supporting URLs; and
5. streams the answer and source cards to the browser.

Search latency is included in displayed TTFT. Basic Search currently consumes
one Tavily credit per enabled request. Web content is explicitly isolated from
instructions to reduce prompt-injection risk.

## Testing and benchmarks

Run the dependency-free local test suite first. It starts a mock Verda upstream
and verifies credential isolation, health proxying, two-message history,
parameter limits, authentication, and SSE streaming without consuming credits:

```bash
npm test
```

Run live endpoint tests only after the deployment reports healthy:

```bash
source scripts/env.sh
export VERDA_ENDPOINT="$(terraform output -raw endpoint_base_url)"

python3 tests/test_inference.py
python3 tests/benchmark_endpoint.py --runs 4 --max-tokens 256
python3 tests/benchmark_concurrency.py --concurrency 4 --max-tokens 256
```

With Quicksilver running, validate the complete web-grounded flow:

```bash
node tests/test_web_search.mjs
```

This test consumes two Tavily Basic Search credits and performs two Verda
inferences. See [BENCHMARK.md](BENCHMARK.md) for methodology, historical
measurements, and limitations.

## Security

- `.env`, `scripts/env.sh`, Terraform state, saved plans, caches, and crash
  artifacts are excluded from version control.
- Provider keys are added only by `server.mjs` and are never returned by
  `/api/config` or embedded in browser assets.
- The server binds to `127.0.0.1` by default.
- Upstream SSE compression is disabled to prevent token buffering.
- Tavily excerpts are treated as untrusted data, not model instructions.

Do not expose the local server directly to the internet. For shared or hosted
use, place it behind TLS, authentication, rate limiting, and request-size
controls. Rotate a credential immediately if it is ever committed or logged.

## Repository structure

```text
public/                 Browser UI
scripts/                Deployment, health, and smoke-test helpers
tests/                  Inference, benchmark, and web-search tests
server.mjs              Local server and protected provider proxy
main.tf                 Verda container and vLLM configuration
variables.tf            Deployment inputs
outputs.tf              Deployment outputs
versions.tf             Terraform/provider requirements
BENCHMARK.md             Measurement methodology and results
```

## License

Released under the [MIT License](LICENSE).
