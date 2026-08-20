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
