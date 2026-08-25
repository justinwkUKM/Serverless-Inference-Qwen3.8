# Verda Qwen3.8 Endpoint Benchmark

## Test configuration

> These are historical RTX PRO 6000/NVFP4 measurements. The selected deployment
> uses an RTX PRO 6000 On-Demand GPU and `unsloth/Qwen3.8-27B-NVFP4`.
> These historical results predate the current On-Demand deployment attempt.

Measurements were collected on 20 August 2026 (Malaysia time) against:

| Component | Configuration |
|---|---|
| Endpoint | Private Verda Serverless endpoint |
| Model | `unsloth/Qwen3.8-27B-NVFP4` |
| Served name | `qwen3.8-27b` |
| vLLM | `v0.26.0`, CUDA 12.9 image |
| GPU | 1x RTX PRO 6000 Blackwell, 96 GB |
| Context limit | 131,072 tokens at benchmark time; 32,768 currently |
| KV cache | FP8 |
| GPU memory utilization | 90% |
| Replica range | 0–1 |
| Request concurrency | 4 |
| Scale-down delay | 60 seconds at benchmark time; 300 seconds currently |
| Streaming | Enabled |
| Thinking | Disabled for repeatability |

The coding prompt contained 81 input tokens and requested a typed Python function with a docstring and usage example. Each response contained approximately 217–221 output tokens.

## Metric definitions

- **Cold readiness:** wall-clock time from the first authenticated `/health` request against a scaled-to-zero deployment until `/health` returned HTTP 200. It includes scheduling, image pulling, model loading, compilation, and warm-up.
- **TTFT:** client-observed time from starting `POST /v1/chat/completions` until the first non-empty streamed content or reasoning delta.
- **Decode throughput:** completion tokens reported by vLLM divided by the time from the first generated delta until the stream completed.
- **End-to-end throughput:** prompt plus completion tokens divided by total request latency.
- **Inter-token latency:** generation duration divided by completion tokens minus one. This is an aggregate approximation based on streamed timing, not GPU-kernel latency.

## Results

### Cold start

| Metric | Result |
|---|---:|
| Time from scale-to-zero to healthy | **483.46 s (8 min 3 s)** |
| Final successful health attempt | 3.37 s |

The gateway closed eight preceding 55-second health attempts while the replica initialized. The cold result includes an approximately three-minute pull of the pinned 8+ GiB vLLM image. Model weights were read from the persistent Ceph-backed cache, followed by model loading, `torch.compile`, CUDA graph capture, and FlashInfer warm-up.

### Sequential warm requests

| Run | TTFT (s) | Decode (tok/s) | Total latency (s) | End-to-end (tok/s) |
|---:|---:|---:|---:|---:|
| 1 | 5.394 | 381.03 | 5.974 | 50.55 |
| 2 | 4.989 | 396.34 | 5.546 | 54.45 |
| 3 | 5.082 | 305.48 | 5.806 | 52.02 |
| 4 | 4.949 | 393.16 | 5.511 | 54.80 |

Across all four warm runs:

| Metric | Result |
|---|---:|
| Mean TTFT | **5.104 s** |
| Median TTFT | **5.036 s** |
| Approximate P95 TTFT | **5.347 s** |
| Mean decode throughput | **369.00 tok/s** |
| Decode range | **305.48–396.34 tok/s** |
| Mean total latency | **5.709 s** |

### Four concurrent warm requests

| Metric | Result |
|---|---:|
| Concurrency | 4 |
| Wall time | 5.984 s |
| Aggregate completion tokens | 871 |
| Aggregate end-to-end output throughput | **145.56 tok/s** |
| Mean per-request TTFT | **5.421 s** |
| P50 per-request TTFT | **5.421 s** |
| Approximate P95 per-request TTFT | **5.422 s** |
| Mean per-request total latency | **5.975 s** |
| Individual decode range | **390.91–397.42 tok/s** |

All four requests began returning tokens at nearly the same time, demonstrating effective continuous batching at the configured concurrency limit.

## Interpretation

- Once warm, decode performance is excellent for an interactive coding model: approximately 369 output tokens/s sequentially in this short-response test.
- The roughly five-second warm TTFT dominates total latency. This includes Verda gateway/queue overhead, prompt processing, scheduler latency, and time until the first SSE delta reaches the client.
- Four simultaneous requests added only about 0.3 seconds to mean TTFT compared with the sequential average.
- Cold start is the main usability concern. A 60-second scale-down delay saves idle GPU time but means an agent invoked after an idle minute can wait around eight minutes in the observed worst case.
- The 128K capacity was verified at benchmark time, but the deployment is now configured for 64K with prefix caching and a 16,384-token batched prefill budget. This benchmark intentionally used a short prompt; long-context prefill latency and memory behavior require a separate test with representative repository content.

## Reproduce

### TTFT optimization matrix

The controlled TTFT runner records HTTP-header, first-SSE-byte, first-token,
decode, total-latency, token-usage, and failure measurements. It writes raw
JSON and a Markdown summary under `benchmarks/runs/`; endpoint URLs and keys
are intentionally excluded from those artifacts.

Print the low-cost smoke matrix without sending traffic:

```bash
bash scripts/benchmark-ttft.sh --phase smoke --mode direct
```

After confirming the endpoint is ready, execute it by adding `--execute`.
Use `--mode proxy` with `QUICKSILVER_URL` to compare application overhead.
The full `baseline` and `final` phases are intentionally explicit because
they send many requests:

```bash
set -a && source .env && source scripts/env.sh && set +a
bash scripts/benchmark-ttft.sh --phase baseline --mode direct --execute
bash scripts/benchmark-ttft.sh --phase final --mode direct --execute
```

Each request has a 120-second default timeout. Pass
`--timeout-seconds 900` only for an intentional cold-start probe. The runner
supports `unique`, `shared-prefix`, and `cache-miss` prompt modes so prefix
caching is measured rather than assumed.

```bash
cd /Users/waqaskhalid/Documents/Local/VerdaServerless
source scripts/env.sh
export VERDA_ENDPOINT="$(terraform output -raw endpoint_base_url)"

# Ensure the endpoint is warm before warm-run comparisons.
./scripts/health.sh

python3 tests/benchmark_endpoint.py \
  --runs 4 \
  --max-tokens 256 \
  --pause-seconds 2

python3 tests/benchmark_concurrency.py \
  --concurrency 4 \
  --max-tokens 256
```

For a true cold measurement, wait until the Console reports zero replicas before sending the first request. Do not compare a cold first run directly with the warm statistics.

## Limitations

- This is a small baseline, not a statistically rigorous load test.
- Network distance and current Verda control-plane load affect client-observed TTFT.
- The response was deliberately capped and thinking was disabled.
- P95 estimates from four samples are directional only.
- Decode throughput calculated from API token counts includes streaming and gateway behavior; it is not a kernel-only benchmark.
- No long-context prompt was transmitted, so long-context quality and prefill performance remain unmeasured.

## TTFT optimization implementation status

The controlled runner and Terraform experiment controls are implemented on
the `feature/ttft-optimization` branch. On 24 August 2026, the first smoke
probe coincided with a Verda image pull and model initialization. The
authenticated `/health` request returned no bytes during the initial probe and
the final bounded 60-second readiness check, so no generation request was
counted as a warm-TTFT sample. The probe was stopped before the 15-minute
upstream deadline.

Once the Console reports the replica ready, run the smoke phase first. Only
after it succeeds should the baseline or candidate matrices be executed.

## Post-optimization verification

On 20 August 2026, after reducing the context limit to 65,536 tokens, enabling
automatic prefix caching, and setting `max_num_batched_tokens=16384`, the
updated replica passed its authenticated health check. The first HTTP/2 health
attempt ended with a gateway framing error; an HTTP/1.1 retry succeeded after
approximately 75 seconds while the replacement replica completed startup.

Three warm streamed requests used the same 81-token prompt and requested 128
output tokens:

| Run | TTFT (s) | Decode (tok/s) | Total latency (s) |
|---:|---:|---:|---:|
| 1 | 3.370 | 310.39 | 3.782 |
| 2 | 3.309 | 334.04 | 3.692 |
| 3 | 3.583 | 330.52 | 3.970 |

The final two-run confirmation measured a mean TTFT of **3.446 seconds** and
mean decode throughput of **332.28 tokens/second**. Compared with the original
5.104-second warm TTFT mean, this is approximately a **32.5% reduction**.
Because the prompt is very short, repeated prefix-cache hits did not materially
change TTFT; the remaining roughly 3.3-second floor is likely dominated by
gateway, queue, and request-serving overhead rather than prompt prefill.

## Current warm endpoint probe — 24 August 2026

The controlled runner was executed against the currently ready endpoint with
128 requested output tokens and thinking disabled. Raw JSON and Markdown
reports are saved under `benchmarks/runs/`:

| Profile | Requests | TTFT mean | TTFT p50 | TTFT p95 | Decode speed | Failures |
|---|---:|---:|---:|---:|---:|---:|
| 50-word unique, sequential | 3 | 14.940 s | 2.397 s | 36.359 s | 384.56 tok/s | 0 |
| 1,000-word shared-prefix, sequential | 3 | 2.629 s | 2.895 s | 2.998 s | 579.93 tok/s | 0 |
| 50-word shared-prefix, four parallel workers | 4 | 2.666 s | 2.637 s | 2.847 s | 386.05 tok/s | 0 |
| Follow-up 50-word unique, sequential | 1 | 2.328 s | 2.328 s | 2.328 s | 392.35 tok/s | 0 |

The 40.133-second first request in the sequential cell is a startup/scale
transition outlier; the following requests and the exact four-request
parallel sample stayed in the 2–3 second TTFT range. A separate three-request
parallel probe after an idle transition measured 49.383–51.359 seconds TTFT,
which confirms that the endpoint can leave the warm path even when a health
surface reports it as available.

### Optimization decision

Do not change the vLLM batching flags based on this short-prompt sample:
decode speed and warm TTFT are already healthy, and prefix caching cannot
materially reduce a roughly 2.5-second gateway/scheduling floor for 125-token
inputs. The next production decision is replica policy:

1. Keep `min_replica_count = 0` for cost-sensitive experiments and accept
   occasional cold/startup latency.
2. Use `min_replica_count = 1` (or a longer scale-down delay) for a strict
   1–3 second interactive TTFT target; this trades idle GPU cost for
   predictable readiness.
3. Repeat the matrix with representative 1K/10K-token prompts and p50/p95/p99
   before changing `max_num_batched_tokens` or enabling more aggressive
   prefill tuning.
