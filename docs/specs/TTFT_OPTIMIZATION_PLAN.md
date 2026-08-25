# TTFT Optimization and Benchmark Plan

> **Status: Implementation in progress — deployment changes remain gated by benchmark evidence**

## Summary

Optimize the existing Qwen3.8-27B NVFP4 deployment through controlled,
one-variable-at-a-time experiments. The current baseline uses a 32K context,
FP8 KV cache, prefix caching, `max_num_batched_tokens=16384`, concurrency 4,
and an RTX Pro 6000 On-Demand GPU.

The experiment will distinguish warm inference, cold-start latency,
prompt-prefill cost, prefix-cache effectiveness, and concurrency queueing
before selecting a final configuration.

## Phase 1 — Improve measurement

- Extend the benchmark driver to record:
  - request dispatch to HTTP headers;
  - first SSE byte;
  - first reasoning or content token;
  - TTFT, total latency, decode tokens/second, and aggregate throughput;
  - actual input/output tokens, failures, and timeout categories.
- Report p50, p95, p99, mean, minimum, and maximum. Use p99 only when at
  least 100 samples are collected.
- Add prompt modes:
  - `unique`, which prevents prefix-cache reuse;
  - `shared-prefix`, which uses a stable system/document prefix and unique
    suffix;
  - `cache-miss`, which makes the entire request unique.
- Save raw per-request JSON and a generated Markdown report in `benchmarks/`.
- Compare direct Verda requests with requests through Quicksilver's
  `/api/chat` proxy to isolate application and proxy overhead.
- Record deployment revision, GPU, model, vLLM image, replica state, context
  limit, scheduler flags, timestamp, and test location with every run.

## Phase 2 — Establish the baseline

Use the current configuration without changes:

- RTX Pro 6000 On-Demand, one replica.
- 32,768-token context.
- FP8 KV cache.
- Prefix caching enabled.
- `max_num_batched_tokens=16384`.
- Four concurrent requests per replica.
- Scale-down delay 300 seconds and minimum replicas 0.

After one warm-up request, run this matrix:

| Input profile | Concurrency | Samples |
|---|---:|---:|
| Approximately 50 tokens | 1, 4, 8 | 20 each |
| Approximately 1K tokens | 1, 4, 8 | 20 each |
| Approximately 10K tokens | 1, 4, 8 | 20 each |

Run both unique-prefix and shared-prefix profiles. Use 128 output tokens,
temperature 0, reasoning disabled, identical model parameters, and actual API
token counts for reporting.

Also run:

- One scale-to-zero cold start, measured separately from warm TTFT.
- A mixed-load test: one 10K request followed shortly by four 50-token
  interactive requests.
- A 100-request short-context concurrency-4 run for meaningful p99 TTFT.

## Phase 3 — Tune vLLM

Test each candidate independently, redeploying and warming the endpoint before
measurement.

### 1. Explicit chunked prefill

- Add `--enable-chunked-prefill`.
- Keep the 16,384 batched-token budget.
- This removes ambiguity even though vLLM 0.26 normally enables chunked
  prefill when supported. See the
  [vLLM 0.26 serve documentation](https://docs.vllm.ai/en/v0.26.0/cli/serve/).

### 2. Batched-token budget

- Compare 8,192, 16,384, and 32,768.
- Use 16,384 as the control.
- Larger budgets can improve TTFT by processing more prefill tokens per
  scheduler iteration, while smaller budgets can favor inter-token latency.
  See the
  [vLLM optimization guidance](https://docs.vllm.ai/en/latest/configuration/optimization/).

### 3. Mixed-workload prefill scheduling

If long prompts delay short prompts, test:

- `--max-num-partial-prefills 2`
- `--max-long-partial-prefills 1`
- `--long-prefill-token-threshold 4096`

This configuration allows short interactive requests to move ahead of
additional long partial prefills.

### 4. Prefix-cache effectiveness

- Compare the first shared-prefix request with subsequent requests.
- Keep system prompts, policies, tool definitions, and document context
  byte-identical at the beginning.
- Put user-specific and request-specific content at the end.
- Do not put unique benchmark text at the beginning when measuring cache hits.

Each candidate first receives a three-request smoke test. Stop that candidate
immediately on startup failure, incorrect output, GPU-memory errors, or
streaming failures. Only successful candidates receive the full matrix.

## Phase 4 — Warm replica and workload policy

Test both deployment modes:

- `min_replica_count=0`: measure one true cold start and warm requests inside
  the five-minute window.
- `min_replica_count=1`: allow startup and kernel warm-up to finish, then run
  the same warm matrix and a 30-minute idle/retest cycle.

Report the incremental GPU cost separately from latency. Do not mix cold-start
samples into warm TTFT percentiles.

If short interactive TTFT still degrades substantially during 10K requests:

- Keep concurrency at four per replica with a hard interactive ceiling of
  eight.
- Recommend a separate long-context/batch endpoint rather than increasing
  per-replica concurrency.
- Test a second replica only after scheduler tuning, using the same matrix to
  verify p95 improvement and scaling efficiency.

## Selection criteria

Choose a configuration only if it satisfies all of these:

- Short-context concurrency 1: warm TTFT p95 at or below 3 seconds.
- Short-context concurrency 4: warm TTFT p95 at or below 4 seconds.
- At least 20% improvement in 1K/10K prompt TTFT or mixed-load interactive
  TTFT.
- Zero failed requests through concurrency 8.
- No more than 10% regression in aggregate completion throughput.
- No more than 10% regression in decode tokens/second.
- Stable Markdown/code output and no reasoning leakage when reasoning is
  disabled.
- Prefix-cache tests show repeatable improvement rather than a one-run anomaly.

If no candidate reaches the target, use the measured phase breakdown to
classify the remaining floor:

- Direct and proxied TTFT both high: Verda gateway, scheduler, or GPU prefill.
- Proxy materially slower: application or network buffering.
- TTFT scales with context: prefill bottleneck.
- TTFT scales with concurrency: queueing or insufficient replicas.
- Only scale-from-zero is slow: cold-start policy.
- Shared prefixes do not improve TTFT: cache misses, unstable prefixes, or
  gateway-dominated latency.

## Deliverables

- Reproducible benchmark commands and runner enhancements.
- Timestamped raw JSON and Markdown reports in `benchmarks/`.
- Baseline-versus-candidate tables for TTFT, latency, decode speed,
  throughput, and failures.
- Recommended vLLM and Verda configuration with rollback values.
- Cost/latency comparison for minimum replicas 0 versus 1.
- A concise results summary and operating limits in README and benchmark
  documentation.

## Assumptions and safeguards

- Tests use the existing RTX Pro 6000 On-Demand deployment and NVFP4 model.
- No H200 or B200 migration is included until the current software and
  scheduling bottlenecks are quantified.
- Configuration changes are sequential, reversible, and never combined
  before their individual effects are measured.
- Live benchmark execution requires explicit confirmation because it consumes
  Verda capacity; Tavily is not involved.
- Cold-start and warm-request results are always reported separately.
