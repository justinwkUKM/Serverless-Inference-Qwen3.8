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
MAX_TOKENS = 4096

TEST_PROMPTS = [
    {
        "id": 1,
        "name": "Kerberos Ticket Forgery (Golden vs Silver Tickets)",
        "prompt": "Provide a comprehensive technical comparison between Kerberos Golden Tickets and Silver Tickets in an Active Directory penetration test. Detail: 1) The exact cryptographic keys used to forge each ticket (KRBTGT vs Service Account NTLM/AES), 2) What components (TGT vs TGS, PAC validation) are constructed, 3) How detection differs in Windows Event Logs (Event IDs 4768, 4769), and 4) Complete defensive remediation strategies."
    },
    {
        "id": 2,
        "name": "Heap Exploitation Mechanics (Use-After-Free & Glibc Tcache)",
        "prompt": "Explain the mechanics of Use-After-Free (UAF) vulnerabilities in C/C++ applications from a security researcher's perspective. Detail: 1) How heap allocators (specifically glibc ptmalloc tcache) manage freed chunks, 2) How stale pointer reuse leads to arbitrary write or control flow hijacking, 3) The evolution of heap mitigations (Safe-Linking in glibc 2.32+, pointer authentication, ASLR), and 4) Secure memory management coding patterns to prevent UAF."
    },
    {
        "id": 3,
        "name": "HTTP Request Smuggling (CL.TE vs TE.CL)",
        "prompt": "Break down HTTP Request Smuggling vulnerabilities caused by frontend/backend proxy desynchronization under RFC 7230. Detail: 1) The differential parsing mechanisms between Content-Length (CL) and Transfer-Encoding (TE) in CL.TE and TE.CL scenarios, 2) Safe verification methodology during an authorized web application penetration test without disrupting production traffic, and 3) Web server and reverse proxy configuration remediations (e.g., HTTP/2 end-to-end, strict header parsing)."
    },
    {
        "id": 4,
        "name": "OAuth 2.0 & OpenID Connect Architecture Flaws",
        "prompt": "Analyze four common architectural vulnerabilities in OAuth 2.0 and OpenID Connect implementations: 1) Authorization code interception without PKCE, 2) State parameter omission leading to Login CSRF, 3) Loose redirect_uri validation leading to token leakage, and 4) IdP / SP token confusion attacks. For each, describe the root cause, how an ethical tester audits for it, and the OAuth 2.1 specification fixes."
    },
    {
        "id": 5,
        "name": "Windows Token Manipulation & SeImpersonatePrivilege",
        "prompt": "Explain Windows Access Token architecture and privilege escalation via SeImpersonatePrivilege in an authorized penetration test. Detail: 1) The technical difference between Primary and Impersonation tokens, 2) The role of Named Pipe impersonation and RPC/DCOM bindings (e.g. Potato-family mechanics conceptually), 3) Windows OS version mitigations introduced in Windows 10 / Server 2019+, and 4) System hardening controls."
    },
    {
        "id": 6,
        "name": "Second-Order SQL Injection & Advanced Evasion",
        "prompt": "Explain the mechanics and lifecycle of Second-Order SQL Injection. Detail: 1) Why traditional WAFs and first-order parameter sanitizers fail to catch it, 2) How data storage, retrieval, and secondary query concatenation trigger the execution phase, 3) How penetration testers audit complex workflows to uncover second-order flaws, and 4) Robust architecture-level remediations using parameterized prepared statements across all application boundaries."
    },
    {
        "id": 7,
        "name": "Linux eBPF Security & Rootkit Architecture Analysis",
        "prompt": "Analyze the security implications of Linux extended Berkeley Packet Filter (eBPF). Detail: 1) How eBPF verifier guarantees kernel safety constraints and its limitations, 2) How an adversary with root capabilities can abuse tracepoints, kprobes, or socket filters to subvert monitoring tools, 3) How defensive tools (like Tetragon, Falco, and bpftool) inspect and audit running eBPF bytecode, and 4) Kernel configuration lockdowns (e.g. kernel.unprivileged_bpf_disabled)."
    },
    {
        "id": 8,
        "name": "Concurrency Flaws & Race Conditions (TOCTOU)",
        "prompt": "Provide a deep dive into Race Conditions and Time-of-Check to Time-of-Use (TOCTOU) vulnerabilities in high-value web applications and operating system binaries. Detail: 1) The window of vulnerability between condition evaluation and state mutation, 2) Concurrency testing methodologies (e.g. HTTP pipelining, multi-threaded timing probes), and 3) Robust mitigations including database pessimistic/optimistic locking, filesystem file descriptor safety (`openat`, `O_NOFOLLOW`), and idempotent state transitions."
    },
    {
        "id": 9,
        "name": "DOM-Based XSS & Modern SPA Framework Internals",
        "prompt": "Analyze DOM-based Cross-Site Scripting (DOM XSS) within modern Single Page Applications (React, Angular, Vue). Detail: 1) Sources and sinks in client-side DOM manipulation, 2) Why naive client-side sanitizers fail against DOM clobbering and template injection, 3) How penetration testers trace dataflow from source to sink using browser developer tools and dynamic taint analysis, and 4) Modern defensive controls including Trusted Types API and strict CSP Level 3 directives."
    },
    {
        "id": 10,
        "name": "Container Breakouts & Linux Capability Abuse",
        "prompt": "Examine container security boundaries and container breakout mechanisms in Kubernetes/Docker environments. Detail: 1) The security risks associated with CAP_SYS_ADMIN, host PID sharing (`--pid=host`), and exposed Docker/CRI sockets, 2) How cgroup v1 release_agent and core_pattern abuse operate conceptually, and 3) Defense-in-depth hardening including user namespaces, rootless containers, AppArmor/SELinux profiles, and seccomp filters."
    }
]

def run_test(test_idx, test_item):
    print(f"\n{'='*70}")
    print(f"Running Test {test_idx}/10: {test_item['name']}")
    print(f"{'='*70}")

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior cybersecurity architect and ethical penetration testing authority. Provide deep, technically rigorous, highly structured explanations covering offensive mechanics, verification methodologies, and defensive controls."
            },
            {
                "role": "user",
                "content": test_item["prompt"]
            }
        ],
        "temperature": 0.6,
        "max_tokens": MAX_TOKENS,
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
    finish_reason = "unknown"

    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
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
                            choice = choices[0]
                            if choice.get("finish_reason"):
                                finish_reason = choice["finish_reason"]
                            delta = choice.get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                if t_first_token is None:
                                    t_first_token = time.time()
                                chunks.append(content)
                    except json.JSONDecodeError:
                        pass
    except Exception as e:
        print(f"Error during test: {e}")
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
        "finish_reason": finish_reason,
        "ttft_s": round(ttft, 3),
        "total_latency_s": round(total_latency, 3),
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "decode_tokens_per_sec": round(decode_tok_s, 2),
        "e2e_tokens_per_sec": round(e2e_tok_s, 2),
    }

    print(f"TTFT:              {result['ttft_s']}s")
    print(f"Total Latency:     {result['total_latency_s']}s")
    print(f"Tokens Generated:  {completion_tokens} (Finish reason: {finish_reason})")
    print(f"Decode Throughput: {result['decode_tokens_per_sec']} tok/s")
    print(f"End-to-End Speed:  {result['e2e_tokens_per_sec']} tok/s")
    print(f"Response Preview:  {full_text[:200]}...")

    return result

def main():
    print(f"Connecting to Endpoint: {ENDPOINT}")
    print(f"Model: {MODEL} | Max Tokens: {MAX_TOKENS}")
    results = []

    for idx, item in enumerate(TEST_PROMPTS, 1):
        res = run_test(idx, item)
        if res:
            results.append(res)

    output_path = "benchmarks/runs/offensive_10_benchmark_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*85)
    print("10-TEST BENCHMARK SUMMARY (max_tokens=4096)")
    print("="*85)
    print(f"{'#':<3} | {'Test Name':<42} | {'TTFT':<7} | {'Total':<7} | {'Tokens':<7} | {'Tok/s':<7} | {'Reason':<6}")
    print("-" * 85)
    for r in results:
        print(f"{r['id']:<3} | {r['name'][:42]:<42} | {r['ttft_s']:<6}s | {r['total_latency_s']:<6}s | {r['completion_tokens']:<7} | {r['decode_tokens_per_sec']:<7} | {r['finish_reason']:<6}")
    
    if results:
        avg_ttft = sum(r['ttft_s'] for r in results) / len(results)
        avg_decode = sum(r['decode_tokens_per_sec'] for r in results) / len(results)
        avg_total_lat = sum(r['total_latency_s'] for r in results) / len(results)
        avg_tokens = sum(r['completion_tokens'] for r in results) / len(results)
        print("-" * 85)
        print(f"Averages: TTFT: {avg_ttft:.3f}s | Decode: {avg_decode:.2f} tok/s | Latency: {avg_total_lat:.3f}s | Output Tokens: {avg_tokens:.1f}")
        print("="*85)

if __name__ == "__main__":
    main()
