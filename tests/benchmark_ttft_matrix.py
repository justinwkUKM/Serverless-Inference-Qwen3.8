#!/usr/bin/env python3
"""Run reproducible TTFT experiments against direct or Quicksilver endpoints.

Only Python's standard library is used. Secrets are read from the environment
and are never included in output files. Results contain the endpoint mode, but
not the endpoint URL.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import platform
import statistics
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path


WORDS = "architecture latency streaming inference scheduler cache tensor context agent code function service data request response token memory queue throughput".split()
SYSTEM_PROMPT = "You are a concise inference performance analyst. Return exactly five short recommendations."


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def rounded(value: float | None, digits: int = 3) -> float | None:
    return None if value is None else round(value, digits)


def make_prompt(target_words: int, run: int, prompt_mode: str) -> str:
    body = " ".join(WORDS[index % len(WORDS)] for index in range(target_words))
    nonce = uuid.uuid4().hex
    instruction = "Analyze the context and return exactly five concise performance recommendations."
    if prompt_mode == "shared-prefix":
        return f"{body}\n\n{instruction}\nRequest identifier: {nonce}"
    if prompt_mode == "cache-miss":
        return f"Request identifier: {nonce}\n\n{body}\n\n{instruction}"
    return f"Unique benchmark run {run}-{nonce}. {instruction}\n\n{body}"


def request_payload(mode: str, prompt: str, max_tokens: int) -> dict:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
    ]
    if mode == "proxy":
        return {
            "request_kind": "ttft benchmark",
            "history_enabled": False,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "enable_thinking": False,
            "web_search": False,
        }
    return {
        "model": "qwen3.8-27b",
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
        "stream": True,
        "stream_options": {"include_usage": True},
        "chat_template_kwargs": {"enable_thinking": False},
    }


def classify_error(error: Exception) -> str:
    text = str(error).lower()
    if "401" in text or "403" in text or "unauthor" in text:
        return "authentication"
    if "timeout" in text or "deadline" in text or "timed out" in text:
        return "timeout"
    if "capacity" in text or "unavailable" in text:
        return "capacity"
    if "stream" in text or "closed" in text or "reset" in text:
        return "stream"
    return "upstream"


def benchmark_once(
    url: str,
    api_key: str | None,
    mode: str,
    target_words: int,
    prompt_mode: str,
    max_tokens: int,
    run: int,
    timeout_seconds: float,
) -> dict:
    prompt = make_prompt(target_words, run, prompt_mode)
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Accept-Encoding": "identity",
        "User-Agent": "quicksilver-ttft-benchmark/2.0",
    }
    if mode == "direct":
        headers["Authorization"] = f"Bearer {api_key}"
    path = "/v1/chat/completions" if mode == "direct" else "/api/chat"
    request = urllib.request.Request(
        f"{url.rstrip('/')}{path}",
        data=json.dumps(request_payload(mode, prompt, max_tokens)).encode(),
        headers=headers,
        method="POST",
    )
    started = time.perf_counter()
    headers_at = first_sse_at = first_token_at = None
    usage: dict = {}
    chunks = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            headers_at = time.perf_counter()
            for raw in response:
                line = raw.decode(errors="replace").strip()
                if not line.startswith("data: "):
                    continue
                if first_sse_at is None:
                    first_sse_at = time.perf_counter()
                data = line[6:].strip()
                if not data or data == "[DONE]":
                    continue
                event = json.loads(data)
                usage = event.get("usage") or usage
                for choice in event.get("choices", []):
                    delta = choice.get("delta") or {}
                    text = delta.get("content") or delta.get("reasoning") or delta.get("reasoning_content") or ""
                    if text:
                        first_token_at = first_token_at or time.perf_counter()
                        chunks += 1
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")[:500]
        raise RuntimeError(f"HTTP {error.code}: {detail}") from error
    finished = time.perf_counter()
    if first_token_at is None or headers_at is None:
        raise RuntimeError("stream ended without generated content")
    completion = int(usage.get("completion_tokens", 0))
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    decode_seconds = max(finished - first_token_at, 1e-9)
    return {
        "run": run,
        "status": "completed",
        "prompt_mode": prompt_mode,
        "target_words": target_words,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion,
        "headers_seconds": rounded(headers_at - started),
        "first_sse_seconds": rounded((first_sse_at or headers_at) - started),
        "ttft_seconds": rounded(first_token_at - started),
        "decode_seconds": rounded(decode_seconds),
        "total_seconds": rounded(finished - started),
        "decode_tokens_per_second": rounded(completion / decode_seconds, 2),
        "stream_chunks": chunks,
    }


def summarize(results: list[dict], errors: list[dict], wall_seconds: float) -> dict:
    ttfts = [item["ttft_seconds"] for item in results]
    totals = [item["total_seconds"] for item in results]
    decode = [item["decode_tokens_per_second"] for item in results]
    completion = sum(item["completion_tokens"] for item in results)
    summary = {
        "successful_requests": len(results),
        "failed_requests": len(errors),
        "ttft_mean_seconds": rounded(statistics.mean(ttfts)) if ttfts else None,
        "ttft_p50_seconds": rounded(percentile(ttfts, 0.50)),
        "ttft_p95_seconds": rounded(percentile(ttfts, 0.95)),
        "ttft_p99_seconds": rounded(percentile(ttfts, 0.99)) if len(ttfts) >= 100 else None,
        "ttft_min_seconds": rounded(min(ttfts)) if ttfts else None,
        "ttft_max_seconds": rounded(max(ttfts)) if ttfts else None,
        "latency_mean_seconds": rounded(statistics.mean(totals)) if totals else None,
        "decode_tps_mean": rounded(statistics.mean(decode), 2) if decode else None,
        "aggregate_completion_tps_wall": rounded(completion / max(wall_seconds, 1e-9), 2),
        "wall_seconds": rounded(wall_seconds),
    }
    return summary


def markdown_report(document: dict) -> str:
    meta, summary = document["metadata"], document["summary"]
    lines = [
        f"# TTFT benchmark — {meta['measured_at']}", "",
        "> Generated by `tests/benchmark_ttft_matrix.py`. Credentials and endpoint URLs are excluded.", "",
        "## Configuration", "",
        f"- Mode: `{meta['endpoint_mode']}`",
        f"- Prompt mode: `{meta['prompt_mode']}`",
        f"- Target words: {meta['target_words']}",
        f"- Concurrency: {meta['concurrency']}",
        f"- Requested output tokens: {meta['max_tokens']}",
        f"- Deployment revision: `{meta['deployment_revision']}`", "",
        "## Summary", "",
        "| Success | Failed | TTFT mean | TTFT p50 | TTFT p95 | TTFT p99 | Decode tok/s | Aggregate tok/s |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {summary['successful_requests']} | {summary['failed_requests']} | {summary['ttft_mean_seconds']} | {summary['ttft_p50_seconds']} | {summary['ttft_p95_seconds']} | {summary['ttft_p99_seconds'] or 'n/a'} | {summary['decode_tps_mean']} | {summary['aggregate_completion_tps_wall']} |",
        "", "## Requests", "",
        "| Run | Status | Input tokens | TTFT (s) | Headers (s) | First SSE (s) | Total (s) | Decode tok/s |",
        "|---:|---|---:|---:|---:|---:|---:|---:|",
    ]
    for item in document["results"]:
        lines.append(f"| {item['run']} | completed | {item['prompt_tokens']} | {item['ttft_seconds']} | {item['headers_seconds']} | {item['first_sse_seconds']} | {item['total_seconds']} | {item['decode_tokens_per_second']} |")
    for item in document["errors"]:
        lines.append(f"| {item['run']} | {item['category']} | — | — | — | — | — | — |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["direct", "proxy"], default="direct")
    parser.add_argument("--target-words", type=int, required=True)
    parser.add_argument("--concurrency", type=int, required=True)
    parser.add_argument("--runs", type=int, default=20)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--prompt-mode", choices=["unique", "shared-prefix", "cache-miss"], default="unique")
    parser.add_argument("--output-dir", default="benchmarks/runs")
    parser.add_argument("--deployment-revision", default=os.environ.get("TTFT_DEPLOYMENT_REVISION", "unrecorded"))
    parser.add_argument("--timeout-seconds", type=float, default=120, help="Per-request timeout; use 900 only for an intentional cold-start probe")
    args = parser.parse_args()
    if args.runs < 1 or args.concurrency < 1 or args.target_words < 1:
        parser.error("runs, concurrency, and target-words must be positive")
    url = os.environ["VERDA_ENDPOINT"] if args.mode == "direct" else os.environ.get("QUICKSILVER_URL", "http://127.0.0.1:4173")
    key = os.environ.get("VERDA_INFERENCE_KEY") if args.mode == "direct" else None
    if args.mode == "direct" and not key:
        parser.error("VERDA_INFERENCE_KEY is required in direct mode")
    started = time.perf_counter()
    results: list[dict] = []
    errors: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = {
            pool.submit(benchmark_once, url, key, args.mode, args.target_words, args.prompt_mode, args.max_tokens, run, args.timeout_seconds): run
            for run in range(1, args.runs + 1)
        }
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
                print(json.dumps({"result": result}), flush=True)
            except Exception as error:  # noqa: BLE001 - benchmark records remote failures
                failure = {"run": futures[future], "category": classify_error(error), "error": str(error)[:500]}
                errors.append(failure)
                print(json.dumps({"error": failure}), flush=True)
    wall = time.perf_counter() - started
    timestamp = datetime.now(timezone.utc)
    document = {
        "metadata": {
            "measured_at": timestamp.isoformat(),
            "endpoint_mode": args.mode,
            "prompt_mode": args.prompt_mode,
            "target_words": args.target_words,
            "concurrency": args.concurrency,
            "runs": args.runs,
            "max_tokens": args.max_tokens,
            "timeout_seconds": args.timeout_seconds,
            "deployment_revision": args.deployment_revision,
            "client_python": platform.python_version(),
            "client_platform": platform.platform(),
        },
        "summary": summarize(results, errors, wall),
        "results": sorted(results, key=lambda item: item["run"]),
        "errors": sorted(errors, key=lambda item: item["run"]),
    }
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{timestamp.strftime('%Y%m%dT%H%M%SZ')}-{args.mode}-{args.prompt_mode}-{args.target_words}w-c{args.concurrency}"
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(document, indent=2) + "\n")
    markdown_path.write_text(markdown_report(document))
    print(json.dumps({"summary": document["summary"], "json": str(json_path), "markdown": str(markdown_path)}, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
