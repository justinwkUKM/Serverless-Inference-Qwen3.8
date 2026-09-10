#!/usr/bin/env python3
import time
import json
import urllib.request
import os
import sys

ENDPOINT = os.getenv("VERDA_ENDPOINT", "http://135.181.8.204:8000").rstrip("/")
API_KEY = os.getenv("VERDA_INFERENCE_KEY")
if not API_KEY:
    print("Error: VERDA_INFERENCE_KEY environment variable is required.", file=sys.stderr)
    sys.exit(1)
MODEL = os.getenv("VERDA_MODEL", "Antanom")

TEST_PROMPTS = [
    {
        "id": 1,
        "name": "Blind SQL Injection (Boolean-based Binary Search)",
        "prompt": "Explain the technical mechanics of Boolean-based Blind SQL Injection. Provide an example SQL query structure vulnerable to this flaw, and explain the algorithmic binary search methodology an ethical tester uses to extract data character by character."
    },
    {
        "id": 2,
        "name": "Linux Privilege Escalation (SUID & PATH Hijacking)",
        "prompt": "In an authorized penetration test, an auditor discovers a custom SUID root binary that invokes an external command via system('service apache2 restart'). Explain the root cause of the PATH manipulation flaw, how the auditor verifies privilege escalation in a lab, and the proper C-level code fix."
    },
    {
        "id": 3,
        "name": "JWT Algorithm Confusion (RS256 vs HS256)",
        "prompt": "Describe the mechanics of JWT algorithm confusion attacks where an asymmetry between RS256 and HS256 is abused. Explain how the vulnerability arises in verification libraries and how a security analyst verifies whether an API endpoint is susceptible."
    },
    {
        "id": 4,
        "name": "Active Directory AS-REP Roasting",
        "prompt": "Explain AS-REP Roasting in an Active Directory penetration test. What specific user account configuration (DONT_REQ_PREAUTH) makes this possible, what network request is sent to the KDC, and how does offline hash cracking work?"
    },
    {
        "id": 5,
        "name": "Cloud SSRF: IMDSv1 vs IMDSv2 Defenses",
        "prompt": "Break down the offensive attack vector of Server-Side Request Forgery (SSRF) against AWS EC2 instance metadata service IMDSv1 versus the defensive protections introduced in IMDSv2 (specifically PUT request token creation and IP hop-limit constraints)."
    }
]

def run_test(test_idx, test_item):
    print(f"\n========================================================")
    print(f"Running Test {test_idx}/5: {test_item['name']}")
    print(f"========================================================")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior ethical penetration tester and cybersecurity researcher. Provide technically precise, structured, and in-depth explanations."
            },
            {
                "role": "user",
                "content": test_item["prompt"]
            }
        ],
        "temperature": 0.6,
        "max_tokens": 768,
        "stream": True,
        "stream_options": {"include_usage": True}
    }

    req = urllib.request.Request(
        f"{ENDPOINT}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }
    )

    t0 = time.time()
    t_first_token = None
    chunks = []
    usage = None

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            for line in resp:
                line_str = line.decode("utf-8", errors="ignore").strip()
                if not line_str or line_str.startswith(":"):
                    continue
                if line_str == "data: [DONE]":
                    break
                if line_str.startswith("data: "):
                    data_json = line_str[6:]
                    try:
                        parsed = json.loads(data_json)
                        if "usage" in parsed and parsed["usage"]:
                            usage = parsed["usage"]
                        choices = parsed.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                if t_first_token is None:
                                    t_first_token = time.time()
                                chunks.append(content)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"Error executing test: {e}")
        return None

    t_end = time.time()
    total_latency = t_end - t0
    ttft = (t_first_token - t0) if t_first_token else total_latency
    full_text = "".join(chunks)

    prompt_tokens = usage.get("prompt_tokens", 0) if usage else len(test_item["prompt"]) // 4
    completion_tokens = usage.get("completion_tokens", len(full_text) // 4) if usage else len(full_text) // 4

    decode_time = max(0.001, total_latency - ttft)
    decode_tok_s = completion_tokens / decode_time if completion_tokens > 0 else 0
    e2e_tok_s = completion_tokens / total_latency if total_latency > 0 else 0

    result = {
        "id": test_item["id"],
        "name": test_item["name"],
        "prompt": test_item["prompt"],
        "response": full_text,
        "ttft_s": round(ttft, 3),
        "total_latency_s": round(total_latency, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "decode_tokens_per_sec": round(decode_tok_s, 2),
        "e2e_tokens_per_sec": round(e2e_tok_s, 2),
    }

    print(f"TTFT (Time To First Token): {result['ttft_s']}s")
    print(f"Total Latency:             {result['total_latency_s']}s")
    print(f"Tokens:                    Prompt: {prompt_tokens} | Completion: {completion_tokens}")
    print(f"Decode Throughput:         {result['decode_tokens_per_sec']} tok/s")
    print(f"End-to-End Speed:          {result['e2e_tokens_per_sec']} tok/s")
    print(f"\nResponse Sample (first 250 chars):\n{full_text[:250]}...\n")

    return result

def main():
    print(f"Connecting to Endpoint: {ENDPOINT}")
    print(f"Target Model: {MODEL}")
    results = []

    for idx, item in enumerate(TEST_PROMPTS, 1):
        res = run_test(idx, item)
        if res:
            results.append(res)

    output_path = "benchmarks/runs/offensive_benchmark_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*70)
    print("BENCHMARK SUMMARY")
    print("="*70)
    print(f"{'#':<3} | {'Test Name':<42} | {'TTFT':<7} | {'Total':<7} | {'Tokens':<6} | {'Tok/s':<7}")
    print("-" * 75)
    for r in results:
        print(f"{r['id']:<3} | {r['name'][:42]:<42} | {r['ttft_s']:<6}s | {r['total_latency_s']:<6}s | {r['completion_tokens']:<6} | {r['decode_tokens_per_sec']:<7}")
    
    if results:
        avg_ttft = sum(r['ttft_s'] for r in results) / len(results)
        avg_decode = sum(r['decode_tokens_per_sec'] for r in results) / len(results)
        avg_total_lat = sum(r['total_latency_s'] for r in results) / len(results)
        print("-" * 75)
        print(f"Averages: TTFT: {avg_ttft:.3f}s | Decode: {avg_decode:.2f} tok/s | Latency: {avg_total_lat:.3f}s")
        print("="*70)

if __name__ == "__main__":
    main()
