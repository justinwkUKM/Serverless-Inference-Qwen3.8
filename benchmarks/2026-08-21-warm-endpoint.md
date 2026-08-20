# Warm endpoint benchmark results

Benchmark date: 21 August 2026 (Asia/Kuala Lumpur)

## Test setup

- Model: Qwen3.8-27B NVFP4
- Endpoint state: warm, one replica
- Maximum completion: 128 tokens per request
- Context tiers: approximately 174, 946, 4,047, and 16,047 input tokens
- Concurrency: 1, 2, 4, 8, 16, 32, and 64
- Prompts contained request-specific text to reduce accidental prefix-cache reuse
- TTFT is measured from request start until the first streamed content token
- Aggregate output TPS is total successful completion tokens divided by test wall time

## Results

| Input tokens | Concurrency | Success | TTFT mean (s) | TTFT p50 (s) | TTFT p95 (s) | Mean latency (s) | Aggregate output tok/s |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 174 | 1 | 1/1 | 2.818 | 2.818 | 2.818 | 3.155 | 25.35 |
| 174 | 2 | 2/2 | 2.994 | 2.994 | 2.995 | 3.404 | 51.67 |
| 174 | 4 | 4/4 | 2.982 | 2.997 | 3.040 | 3.314 | 102.52 |
| 174 | 8 | 8/8 | 3.499 | 3.006 | 4.623 | 3.805 | 135.12 |
| 174 | 16 | 16/16 | 5.149 | 4.744 | 7.843 | 5.458 | 167.30 |
| 174 | 32 | 32/32 | 8.330 | 8.286 | 14.055 | 8.628 | 182.45 |
| 174 | 64 | 64/64 | 14.497 | 14.381 | 25.922 | 14.814 | 196.66 |
| 946 | 1 | 1/1 | 2.690 | 2.690 | 2.690 | 3.075 | 28.29 |
| 946 | 2 | 2/2 | 2.995 | 2.995 | 2.995 | 3.324 | 54.39 |
| 946 | 4 | 4/4 | 3.263 | 3.099 | 3.687 | 3.633 | 93.44 |
| 946 | 8 | 8/8 | 3.804 | 3.280 | 5.006 | 4.114 | 129.53 |
| 946 | 16 | 16/16 | 5.643 | 5.351 | 8.685 | 5.985 | 152.89 |
| 946 | 32 | 32/32 | 9.272 | 9.047 | 16.124 | 9.592 | 172.15 |
| 946 | 64 | 64/64 | 16.879 | 16.799 | 29.225 | 17.181 | 179.43 |
| 4,047 | 1 | 1/1 | 3.352 | 3.352 | 3.352 | 3.689 | 24.39 |
| 4,047 | 2 | 2/2 | 3.415 | 3.415 | 3.717 | 3.641 | 38.76 |
| 4,047 | 4 | 4/4 | 3.775 | 3.860 | 3.939 | 3.986 | 71.24 |
| 4,047 | 8 | 8/8 | 4.891 | 4.585 | 6.322 | 5.171 | 102.21 |
| 4,047 | 16 | 16/16 | 7.544 | 7.501 | 10.870 | 7.835 | 120.39 |
| 4,047 | 32 | 32/32 | 11.537 | 11.040 | 19.638 | 11.815 | 134.65 |
| 4,047 | 64 | 64/64 | 21.873 | 21.553 | 38.314 | 22.208 | 144.28 |
| 16,047 | 1 | 1/1 | 5.285 | 5.285 | 5.285 | 5.612 | 16.57 |
| 16,047 | 2 | 2/2 | 4.768 | 4.768 | 5.056 | 4.960 | 27.95 |
| 16,047 | 4 | 4/4 | 6.319 | 6.428 | 6.482 | 6.595 | 53.73 |
| 16,047 | 8 | 8/8 | 8.942 | 8.890 | 10.606 | 9.221 | 62.42 |
| 16,047 | 16 | 16/16 | 13.463 | 13.672 | 18.271 | 13.717 | 72.09 |
| 16,047 | 32 | 32/32 | 21.777 | 20.758 | 35.161 | 22.025 | 74.55 |
| 16,047 | 64 | 58/64 | 35.640 | 34.416 | 64.066 | 35.954 | 74.56 |

## Findings

1. The endpoint is healthy at low load. A recovery request after all stress tests completed successfully with 2.528-second TTFT and 2.938-second total latency.
2. For interactive short-context chat, concurrency 4 is the best quality/throughput point: TTFT stays around 3 seconds while aggregate output reaches about 94–103 tok/s.
3. Concurrency 8 is usable for short contexts, but p95 TTFT rises to roughly 4.6–6.3 seconds. Beyond concurrency 8, queueing becomes increasingly visible.
4. Short-context throughput continues increasing through concurrency 64, but with poor interactive latency. For 174-token prompts, moving from concurrency 16 to 64 adds only 18% aggregate throughput while mean TTFT increases 182%.
5. Long-context prefill is the limiting workload. At approximately 16K input tokens, aggregate output throughput plateaus at about 74.5 tok/s by concurrency 32. Concurrency 64 provides no throughput gain, raises p95 TTFT to 64 seconds, and causes a 9.4% request failure rate.
6. The concurrency-64, 16K-context failures were remote connection closures. This is the tested overload boundary; it should not be used as a production operating point.

## Improvements to perform

### Priority 1 — protect interactive latency

- Add an application-side concurrency limiter with a target of four in-flight requests per replica and a hard interactive ceiling of eight.
- Return an explicit queued state to the UI and expose queue time separately from model TTFT.
- Apply request timeouts and bounded retries for transport failures. Do not automatically retry generation after streamed output has begun.
- Keep stream cancellation support so abandoned requests release server capacity quickly.

### Priority 2 — reduce prefill cost

- Keep routine chat prompts below 4K input tokens through token-aware history truncation.
- Summarize older turns before removing them so important user context survives.
- Preserve stable system and conversation prefixes to benefit from vLLM prefix caching.
- Do not send unused web-search excerpts, image payloads, or historical metadata to the model.

### Priority 3 — scale capacity predictably

- Add replicas when sustained interactive demand exceeds eight concurrent requests; do not raise per-replica concurrency to 32 or 64.
- Route long-context jobs to a separate queue or workload class so they cannot delay short interactive prompts.
- Add server-side metrics for queue depth, running/waiting requests, KV-cache utilization, prefix-cache hit rate, prefill throughput, GPU utilization, and errors.
- Repeat the matrix with two replicas to verify scaling efficiency and tail latency before changing production limits.

### Priority 4 — improve measurement quality

- Record raw event timestamps and results as JSON or CSV for regression comparisons.
- Separate gateway/network delay, queue delay, model prefill, and first visible content time where platform telemetry permits.
- Use fixed completion lengths for capacity comparisons and a separate realistic-chat suite for user-experience measurements.
- Run at least three repetitions per matrix cell and report confidence intervals before treating small differences as meaningful.

## Recommended operating limits

- Interactive traffic: target concurrency 4; permit bursts to 8.
- Queue or reject excess requests above 8 per replica if low TTFT is the priority.
- Long contexts (around 16K): target concurrency 2–4; keep below 8 for user-facing traffic.
- For concurrency above 8 with predictable latency, add replicas and load-balance instead of increasing per-replica concurrency.
- Apply dynamic history truncation/summarization so ordinary chat requests usually remain below 4K input tokens.
- Track TTFT separately from decode rate. Decode throughput remains strong after generation starts, while prefill and queue wait dominate perceived latency.

## Measurement caveat

Some concurrent streams arrived in buffered bursts. This makes client-observed per-request decode TPS unrealistically high for those individual responses. Aggregate completion TPS over wall time is the trustworthy capacity measurement in this report. TTFT and total latency remain directly useful client-observed measurements.

The reproducible benchmark driver is `tests/benchmark_context_concurrency.py`.
