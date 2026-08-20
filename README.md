# Quicksilver

Private, OpenAI-compatible inference on Verda Serverless with Qwen3.8, vLLM,
streaming Markdown, performance telemetry, and optional Tavily web grounding.

Quicksilver combines reproducible Terraform infrastructure with a lightweight
local chat console. Secrets remain in the server process: the browser never
receives the Verda inference key, infrastructure credentials, or Tavily key.

## Highlights

- Qwen3.8 27B FP8 served through vLLM's OpenAI-compatible API
- Sanitized GitHub-flavored Markdown with tables, code copy, and responsive images
- Conversational continuity with a bounded 12-message context window
- Collapsible SQLite conversation sidebar with immediate new-chat creation
- Privacy toggle for temporary chats with no context replay or SQLite writes
- Multilingual and bidirectional text rendering for CJK, Arabic, Urdu, Hindi, and more
- Up to four images plus two PDF or text-document attachments per message
- Client-observed TTFT, total latency, token usage, and decode throughput
- Manual health checks plus comparable warm and cold-test controls
- Optional Tavily search with linked sources and prompt-injection boundaries
- Server-side credential proxy with uncompressed SSE for immediate token flush
- Terraform-managed Verda Serverless deployment with scale-to-zero
- Lightweight Node.js server with built-in SQLite persistence

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
| Default reasoning | Disabled server-side; request override supported |
| Replica range | 0–1 |
| Scale-down delay | 300 seconds |

The image uses a versioned tag because Verda does not accept moving tags such
as `latest`. The RTX PRO 6000 On-Demand configuration was listed at $2.079/GPU-hour when
selected; actual capacity and pricing depend on Verda's current compute market.

## Prerequisites

- Node.js 22.13 or newer (for the built-in SQLite module)
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
QUICKSILVER_DB_PATH=data/quicksilver.sqlite
```

`VERDA_INFERENCE_KEY` is read from the process environment first and falls
back to the ignored `scripts/env.sh`. `TAVILY_API_KEY` and `VERDA_ENDPOINT`
can be supplied through the process environment or ignored `.env` file.

Start the console:

```bash
npm start
```

Open <http://127.0.0.1:4173>.

## Chat history and metrics

Quicksilver stores chat history locally in SQLite. The default database is
`data/quicksilver.sqlite`; override it with `QUICKSILVER_DB_PATH`. The database,
WAL files, and all `.sqlite` files are ignored by Git.

The normalized schema keeps:

- chats with a generated ID, title, and creation/update timestamps;
- user and assistant messages, including partial responses when stopped; and
- request status, model, request kind, web-search/reasoning flags, temperature,
  token limit, TTFT, total latency, Tavily latency, token usage, errors, and
  extensible JSON metadata.

Select **New chat** to start a separate conversation. Read-only local APIs are
available at `GET /api/chats` and `GET /api/chats/:id`. These routes intentionally
never expose provider credentials. Because prompts and responses may contain
sensitive material, protect and back up the database appropriately and do not
publish it as an application artifact.

The active chat ID is retained in browser storage and restored from SQLite when
the page reloads. Each inference receives the latest 12 user/assistant messages
plus a server-controlled conversational instruction. This provides useful
short-term memory without allowing conversation context to grow indefinitely.

The default and maximum completion budget is 20,480 tokens. This budget shares
the model's 65,536-token context window with conversation history, system text,
web research, and image tokens. Quicksilver displays an explicit warning when a
response reaches the selected output limit.

vLLM also receives a server-level `enable_thinking=false` default, while the UI
Reasoning toggle can override it per request. Each saved request records the
time to the first upstream byte, first reasoning delta, and first visible-content
delta. The metrics panel uses these phases to distinguish model/gateway waiting
from visible response rendering.

The left conversation sidebar lists all locally stored chats newest-first and
can be collapsed. Empty chats are inserted into SQLite immediately. The first
prompt automatically replaces “New chat” with a concise title; users can rename,
favorite, unfavorite, or permanently delete any chat from its sidebar actions.
Favorites remain above other conversations. Uploaded
images are previewed before sending, limited to four files of 4 MB each, stored
with the local user message, and forwarded as OpenAI-compatible `image_url`
content blocks. PDF, TXT, Markdown, and CSV files can also be attached. PDFs are
limited to 8 MB and 100 pages; text documents are limited to 2 MB. The server
extracts at most 50,000 characters per document, marks the content as an
attachment, and includes it in the same token-aware context budget. Up to two
documents are accepted per message and retained in SQLite for follow-up
questions. Model responses are rendered through sanitized GitHub-flavored
Markdown, including tables, fenced code with copy controls, links, and images.
Text direction is detected automatically for multilingual and mixed RTL/LTR
content.

The composer keeps secondary controls inside an animated `+` menu. Hover,
keyboard focus, or a tap reveals image upload, Web Search, history mode, health,
cold/warm benchmarks, and generation settings. Disabling **Chat history** keeps
the current chat and its visible messages in place, but only the current user
message is sent and no new prompts, responses, attachments, or metrics are
written to SQLite. Re-enabling history does not create a new chat: subsequent
requests again use the messages retained in the current browser session as
context. Warm tests select non-repeating prompts from a curated bank to reduce
identical-prefix bias.

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

1. sends the latest user query to Tavily Basic Search, expanding terse follow-ups
   such as “try again” with the relevant conversational topic;
2. keeps up to five ranked source excerpts;
3. injects them as untrusted reference material;
4. instructs the model to cite supporting URLs; and
5. streams the answer and displays only source cards actually cited by it.

If the model cites none of the returned results, the UI shows an explicit
unverified-answer warning instead of presenting unrelated search results as
references.

Search latency is included in displayed TTFT. Basic Search currently consumes
one Tavily credit per enabled request. Web content is explicitly isolated from
instructions to reduce prompt-injection risk.

## Testing and benchmarks

Run the dependency-free local test suite first. It starts a mock Verda upstream
and verifies credential isolation, health proxying, bounded conversation history,
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
inferences.

### Latest warm-endpoint results

The 21 August 2026 single-replica test covered approximately 174, 946, 4,047,
and 16,047 input tokens at concurrency levels from 1 through 64. Completions
were capped at 128 tokens.

| Workload | Recommended concurrency | Mean TTFT | P95 TTFT | Aggregate output |
|---|---:|---:|---:|---:|
| 174-token input | 4 | 2.98 s | 3.04 s | 102.5 tok/s |
| 946-token input | 4 | 3.26 s | 3.69 s | 93.4 tok/s |
| 4K-token input | 4 | 3.78 s | 3.94 s | 71.2 tok/s |
| 16K-token input | 2–4 | 4.77–6.32 s | 5.06–6.48 s | 28–54 tok/s |

Concurrency four is the recommended interactive operating point, with bursts
up to eight. At 16K input tokens and concurrency 64, only 58 of 64 requests
succeeded, p95 TTFT reached 64.07 seconds, and aggregate output remained flat
at 74.56 tok/s. This confirms that long-context prefill and queueing—not decode
speed—are the primary latency constraints. The endpoint recovered after the
stress test with a 2.53-second TTFT.

See the [detailed warm-endpoint report](benchmarks/2026-08-21-warm-endpoint.md)
for the full 28-scenario matrix, methodology, caveats, observations, and
prioritized improvements.

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
See [Security analysis](docs/SECURITY_ANALYSIS.md) for the reviewed controls,
remaining risks, and production-hardening requirements.

## Repository structure

```text
public/                 Browser UI
benchmarks/             Benchmark reports and reproducible performance results
scripts/                Deployment, health, and smoke-test helpers
tests/                  Inference, benchmark, and web-search tests
server.mjs              Local server and protected provider proxy
main.tf                 Verda container and vLLM configuration
variables.tf            Deployment inputs
outputs.tf              Deployment outputs
versions.tf             Terraform/provider requirements
```

## License

Released under the [MIT License](LICENSE).
