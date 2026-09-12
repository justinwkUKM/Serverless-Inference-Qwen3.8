#!/usr/bin/env python3
import sys
import socket
import struct
import json
import re

max_prompts = int(sys.argv[1]) if len(sys.argv) > 1 else 3
captured = 0

print(f"[*] Live Inspector: Listening for incoming prompts on port 8000...")
print(f"[*] Will automatically stop after capturing {max_prompts} prompt(s).")
print("[*] Waiting for incoming traffic (press Ctrl+C to cancel anytime)...")
print("=" * 65, flush=True)

raw_sock = socket.socket(socket.AF_PACKET, socket.SOCK_RAW, socket.ntohs(0x0800))

while captured < max_prompts:
    try:
        packet, addr = raw_sock.recvfrom(65535)
    except KeyboardInterrupt:
        print("\n[*] Stopped by user.")
        break

    if len(packet) < 34:
        continue

    # IP header (starts at byte 14 after Ethernet header)
    ip_header = packet[14:34]
    iph = struct.unpack("!BBHHHBBH4s4s", ip_header)
    version_ihl = iph[0]
    ihl = version_ihl & 0xF
    iph_length = ihl * 4
    protocol = iph[6]

    if protocol != 6:  # TCP only
        continue

    src_ip = socket.inet_ntoa(iph[8])
    dst_ip = socket.inet_ntoa(iph[9])

    # Skip internal loopback / watchdog health checks
    if src_ip in ("127.0.0.1", "172.17.0.1"):
        continue

    tcp_start = 14 + iph_length
    if len(packet) < tcp_start + 20:
        continue

    tcp_header = packet[tcp_start : tcp_start + 20]
    tcph = struct.unpack("!HHLLBBHHH", tcp_header)
    src_port = tcph[0]
    dst_port = tcph[1]

    # Look for traffic destined to port 8000
    if dst_port != 8000:
        continue

    data_offset = (tcph[4] >> 4) * 4
    payload = packet[tcp_start + data_offset :]
    if not payload:
        continue

    try:
        text = payload.decode("utf-8", errors="ignore")
    except Exception:
        continue

    if "POST /v1/chat/completions" in text or '"messages"' in text:
        # Extract json payload
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            candidate = text[first_brace : last_brace + 1]
            try:
                data = json.loads(candidate)
                if "messages" in data:
                    captured += 1
                    print(f"\n[+] Captured Prompt #{captured}/{max_prompts} | Client: {src_ip}:{src_port}")
                    print(f"    Model: {data.get('model', 'Antanom')}")
                    print("    Messages:")
                    for msg in data.get("messages", []):
                        role = msg.get("role", "user").upper()
                        content = msg.get("content", "")
                        print(f"      - [{role}]: {content}")
                    print("-" * 65, flush=True)
            except Exception:
                # If partial JSON or chunked
                if '"messages"' in candidate:
                    captured += 1
                    print(f"\n[+] Captured Request Chunk #{captured}/{max_prompts} | Client: {src_ip}:{src_port}")
                    print(f"    {candidate[:300]}...")
                    print("-" * 65, flush=True)

print(f"\n[✓] Finished capturing {captured} prompt(s). Server remains unaffected and running.")
