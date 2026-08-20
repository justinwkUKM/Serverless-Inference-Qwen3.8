#!/usr/bin/env python3
"""Benchmark warm vLLM inference across context sizes and concurrency levels."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

from benchmark_endpoint import percentile


WORDS = "architecture latency streaming inference scheduler cache tensor context agent code function service data request response token memory queue throughput".split()


def make_prompt(target_words: int, run: int) -> str:
    prefix = f"Unique benchmark run {run}. Analyze the synthetic context and reply with exactly five concise performance recommendations.\n\n"
    body = " ".join(WORDS[(index + run * 7) % len(WORDS)] for index in range(target_words))
    return prefix + body


def benchmark(endpoint: str, key: str, target_words: int, max_tokens: int, run: int) -> dict:
    payload = {
        "model": "qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "You are a concise inference performance analyst."},
            {"role": "user", "content": make_prompt(target_words, run)},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = urllib.request.Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "text/event-stream", "Accept-Encoding": "identity"},
        method="POST",
    )
    started = time.perf_counter()
    first = None
    usage: dict = {}
    with urllib.request.urlopen(request, timeout=900) as response:
        for raw in response:
            line = raw.decode(errors="replace").strip()
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            event = json.loads(line[6:])
            usage = event.get("usage") or usage
            if first is None and any((choice.get("delta") or {}).get("content") or (choice.get("delta") or {}).get("reasoning") or (choice.get("delta") or {}).get("reasoning_content") for choice in event.get("choices", [])):
                first = time.perf_counter()
    finished = time.perf_counter()
    if first is None:
        raise RuntimeError("stream ended without content")
    completion = int(usage.get("completion_tokens", 0))
    prompt = int(usage.get("prompt_tokens", 0))
    generation = max(finished - first, 1e-9)
    return {
        "run": run,
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "ttft_seconds": round(first - started, 3),
        "total_seconds": round(finished - started, 3),
        "decode_tokens_per_second": round(completion / generation, 2),
        "prompt_tokens_per_ttft_second": round(prompt / max(first - started, 1e-9), 2),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-words", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--max-tokens", type=int, default=128)
    args = parser.parse_args()
    endpoint = os.environ["VERDA_ENDPOINT"]
    key = os.environ["VERDA_INFERENCE_KEY"]
    started = time.perf_counter()
    results, errors = [], []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {pool.submit(benchmark, endpoint, key, args.target_words, args.max_tokens, run): run for run in range(1, args.concurrency + 1)}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as error:
                errors.append({"run": futures[future], "error": str(error)[:300]})
    wall = time.perf_counter() - started
    ttfts = [item["ttft_seconds"] for item in results]
    totals = [item["total_seconds"] for item in results]
    completion = sum(item["completion_tokens"] for item in results)
    summary = {
        "target_words": args.target_words,
        "concurrency": args.concurrency,
        "successful_requests": len(results),
        "failed_requests": len(errors),
        "actual_prompt_tokens_mean": round(statistics.mean(item["prompt_tokens"] for item in results), 1) if results else None,
        "ttft_mean_seconds": round(statistics.mean(ttfts), 3) if ttfts else None,
        "ttft_p50_seconds": round(percentile(ttfts, .5), 3) if ttfts else None,
        "ttft_p95_seconds": round(percentile(ttfts, .95), 3) if ttfts else None,
        "latency_mean_seconds": round(statistics.mean(totals), 3) if totals else None,
        "decode_tps_mean": round(statistics.mean(item["decode_tokens_per_second"] for item in results), 2) if results else None,
        "aggregate_completion_tps_wall": round(completion / max(wall, 1e-9), 2),
        "wall_seconds": round(wall, 3),
        "results": sorted(results, key=lambda item: item["run"]),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
