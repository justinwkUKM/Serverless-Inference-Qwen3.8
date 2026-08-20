#!/usr/bin/env python3
"""Run concurrent streaming requests against the warm Verda endpoint."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

from benchmark_endpoint import benchmark_once, percentile


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=256)
    args = parser.parse_args()

    endpoint = os.environ["VERDA_ENDPOINT"]
    api_key = os.environ["VERDA_INFERENCE_KEY"]
    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(
                benchmark_once, endpoint, api_key, args.max_tokens, run
            )
            for run in range(1, args.concurrency + 1)
        ]
        results = [future.result() for future in futures]
    elapsed = time.perf_counter() - started

    completion_tokens = sum(r["completion_tokens"] for r in results)
    summary = {
        "concurrency": args.concurrency,
        "wall_seconds": round(elapsed, 3),
        "aggregate_completion_tokens": completion_tokens,
        "aggregate_output_tokens_per_second": round(completion_tokens / elapsed, 2),
        "request_ttft_mean_seconds": round(
            statistics.mean(r["time_to_first_token_seconds"] for r in results), 3
        ),
        "request_ttft_p50_seconds": round(
            percentile([r["time_to_first_token_seconds"] for r in results], 0.5), 3
        ),
        "request_ttft_p95_seconds": round(
            percentile([r["time_to_first_token_seconds"] for r in results], 0.95), 3
        ),
        "request_latency_mean_seconds": round(
            statistics.mean(r["total_latency_seconds"] for r in results), 3
        ),
        "individual_results": results,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
