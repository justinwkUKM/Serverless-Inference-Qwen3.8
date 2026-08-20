#!/usr/bin/env python3
"""Measure streaming latency and throughput for the Verda vLLM endpoint.

Uses only the Python standard library. Credentials are read from the
environment and are never printed or written to the results.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


PROMPT = """Implement a production-quality Python function named
deduplicate_events(events) that keeps the newest event for each event_id.
Include type hints, a docstring, deterministic ordering, and a short usage
example. Return only the code and keep the response under 220 tokens."""


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def benchmark_once(endpoint: str, api_key: str, max_tokens: int, run: int) -> dict:
    payload = {
        "model": "qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "You are a precise coding assistant."},
            {"role": "user", "content": PROMPT},
        ],
        "temperature": 0.0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
            "User-Agent": "verda-qwen-benchmark/1.0",
        },
        method="POST",
    )

    started = time.perf_counter()
    first_token_at = None
    content_chunks = 0
    response_chars = 0
    usage = {}

    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            headers_at = time.perf_counter()
            for raw_line in response:
                line = raw_line.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data == "[DONE]":
                    break
                chunk = json.loads(data)
                if chunk.get("usage"):
                    usage = chunk["usage"]
                for choice in chunk.get("choices", []):
                    delta = choice.get("delta") or {}
                    generated = (delta.get("content") or "") + (
                        delta.get("reasoning") or delta.get("reasoning_content") or ""
                    )
                    if generated:
                        if first_token_at is None:
                            first_token_at = time.perf_counter()
                        content_chunks += 1
                        response_chars += len(generated)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code}: {body[:500]}") from error

    finished = time.perf_counter()
    if first_token_at is None:
        raise RuntimeError("The stream completed without a generated token")

    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    generation_seconds = max(finished - first_token_at, 1e-9)
    total_seconds = finished - started

    return {
        "run": run,
        "http_headers_seconds": round(headers_at - started, 3),
        "time_to_first_token_seconds": round(first_token_at - started, 3),
        "generation_seconds": round(generation_seconds, 3),
        "total_latency_seconds": round(total_seconds, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
        "output_tokens_per_second": round(completion_tokens / generation_seconds, 2),
        "end_to_end_tokens_per_second": round(
            (prompt_tokens + completion_tokens) / total_seconds, 2
        ),
        "mean_inter_token_latency_ms": round(
            1000 * generation_seconds / max(completion_tokens - 1, 1), 2
        ),
        "stream_content_chunks": content_chunks,
        "response_characters": response_chars,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=2.0,
        help="Pause between warm requests; keep below the scale-down delay.",
    )
    args = parser.parse_args()

    endpoint = os.environ["VERDA_ENDPOINT"]
    api_key = os.environ["VERDA_INFERENCE_KEY"]
    results = []
    for run in range(1, args.runs + 1):
        result = benchmark_once(endpoint, api_key, args.max_tokens, run)
        results.append(result)
        print(json.dumps({"result": result}), flush=True)
        if run < args.runs:
            time.sleep(args.pause_seconds)

    warm = results
    summary = {
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "model": "qwen3.8-27b",
        "max_model_len": 32768,
        "runs": len(results),
        "prewarm_required_for_comparable_warm_results": True,
        "runs_summarized": len(warm),
        "warm_ttft_mean_seconds": round(
            statistics.mean(r["time_to_first_token_seconds"] for r in warm), 3
        ),
        "warm_ttft_p50_seconds": round(
            percentile([r["time_to_first_token_seconds"] for r in warm], 0.50), 3
        ),
        "warm_ttft_p95_seconds": round(
            percentile([r["time_to_first_token_seconds"] for r in warm], 0.95), 3
        ),
        "warm_output_tps_mean": round(
            statistics.mean(r["output_tokens_per_second"] for r in warm), 2
        ),
        "warm_output_tps_min": round(
            min(r["output_tokens_per_second"] for r in warm), 2
        ),
        "warm_output_tps_max": round(
            max(r["output_tokens_per_second"] for r in warm), 2
        ),
        "warm_total_latency_mean_seconds": round(
            statistics.mean(r["total_latency_seconds"] for r in warm), 3
        ),
    }
    print(json.dumps({"summary": summary}, indent=2))


if __name__ == "__main__":
    main()
