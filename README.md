# Quicksilver

Quicksilver is a private chat interface for Qwen3.8 running on Verda Serverless.
It provides streamed Markdown responses, local conversation history, file
uploads, web search, and inference metrics without exposing provider keys to the
browser.

## Features

- Qwen3.8 27B NVFP4 served through vLLM's OpenAI-compatible API
- Streaming Markdown with code, tables, images, and multilingual text
- SQLite chat history with rename, favorite, delete, and private-session modes
- PDF, text, Markdown, CSV, and image attachments
- Optional Tavily web search with contextual follow-up queries and citations
- TTFT, latency, throughput, token usage, health, warm, and cold measurements
- Four-window mode for comparing the same prompt under concurrent load
- Terraform-managed Verda deployment with scale-to-zero

## Architecture

```text
Browser → Quicksilver server → Verda Serverless → vLLM + Qwen3.8
                    └───────→ Tavily Search (optional)
```

Provider credentials remain on the Quicksilver server.

## Requirements

- Node.js 22.13+
- Terraform 1.x
- Verda API and inference credentials
- Tavily API key only when Web Search is needed

## Local setup

```bash
git clone https://github.com/justinwkUKM/Serverless-Inference-Qwen3.8.git
cd Serverless-Inference-Qwen3.8
npm install

cp scripts/env.example scripts/env.sh
cp .env.example .env
chmod 600 scripts/env.sh .env
```

Add the Terraform and inference credentials to `scripts/env.sh`:

```bash
export VERDA_CLIENT_ID="PASTE_YOUR_CLIENT_ID"
export VERDA_CLIENT_SECRET="PASTE_YOUR_CLIENT_SECRET"
export VERDA_INFERENCE_KEY="PASTE_YOUR_INFERENCE_KEY"
export VERDA_ENDPOINT="https://your-verda-endpoint.example"
```

Configure the local application in `.env`:

```bash
VERDA_ENDPOINT=https://your-verda-endpoint.example
TAVILY_API_KEY=PASTE_YOUR_TAVILY_API_KEY
QUICKSILVER_DB_PATH=data/quicksilver.sqlite
```

Start Quicksilver:

```bash
npm start
```

Open [http://127.0.0.1:4173](http://127.0.0.1:4173).

## Deploy to Verda

The current profile uses Qwen3.8 27B NVFP4 on one RTX PRO 6000 On-Demand GPU,
a 32,768-token context, FP8 KV cache, prefix caching, and a 300-second
scale-down delay.

```bash
source scripts/env.sh
./scripts/deploy.sh
```

After deployment:

```bash
export VERDA_ENDPOINT="$(terraform output -raw endpoint_base_url)"
./scripts/health.sh
./scripts/test.sh
```

Remove the deployment and persistent cache with `./scripts/destroy.sh`.

## Files and conversation context

Quicksilver stores chats and metrics in `data/quicksilver.sqlite`, which is
ignored by Git. It sends a bounded recent history and dynamically removes older
messages when the context budget is reached.

Each message supports up to four 4 MB images and two documents. PDFs are limited
to 8 MB and 100 pages; TXT, Markdown, and CSV files are limited to 2 MB. The
server extracts up to 50,000 characters per document and treats the content as
untrusted reference material.

## Web Search

Enable **Web Search** from the composer menu. Quicksilver expands short
follow-ups such as “try again” with the relevant conversation topic, retrieves
up to five Tavily results, and shows only references cited by the answer. An
explicit warning appears when no result was cited.

Each enabled request uses one Tavily Basic Search credit.

## Testing

Run the local test suite without consuming inference or Tavily credits:

```bash
npm test
```

Run live benchmarks only against a healthy endpoint:

```bash
python3 tests/test_inference.py
python3 tests/benchmark_endpoint.py --runs 4 --max-tokens 256
python3 tests/benchmark_concurrency.py --concurrency 4 --max-tokens 256
node tests/test_web_search.mjs
```

The web-search test consumes two Tavily credits and performs two inferences.

## Performance summary

Warm single-replica testing found concurrency 4 to be the best interactive
operating point, with bursts up to 8. At short context, concurrency 4 produced
approximately 3-second mean TTFT and 94–103 aggregate output tokens/second.
Long 16K-token contexts should remain around concurrency 2–4.

See the [full benchmark report](benchmarks/2026-08-21-warm-endpoint.md) for the
28-scenario matrix and recommendations.

Select **Concurrency 4** in the header to send one shared prompt to four
simultaneous, ephemeral streams. Each window reports its own TTFT, throughput,
latency, and token usage, while the summary bar shows aggregate batch metrics.

## Security

- Secrets, Terraform state, SQLite files, and local environment files are
  excluded from Git.
- Provider keys are injected by the server and never returned to the browser.
- Markdown is sanitized and uploaded content is bounded.
- The server binds to `127.0.0.1` by default.

Do not expose Quicksilver directly to the internet. Shared deployments require
TLS, authentication, authorization, rate limiting, and encrypted storage. See
the [security analysis](docs/SECURITY_ANALYSIS.md) for details.

## Documentation

- [Benchmark results](benchmarks/2026-08-21-warm-endpoint.md)
- [Security analysis](docs/SECURITY_ANALYSIS.md)
- [Google ADK implementation plan](docs/Implementation%20plan%20for%20ADK.md)

## License

Released under the [MIT License](LICENSE).
