#!/bin/bash
set -e

# Setup audit log directory and world-readable audit log
mkdir -p /var/log/audit
cat << 'EOF' > /var/log/audit/sysdaemon.log
[2026-09-18 10:00:01] [INFO] System audit trace initialized.
[2026-09-18 10:00:02] [DEBUG] Local cluster supervisor daemon started on 127.0.0.1:9090.
[2026-09-18 10:00:02] [DEBUG] Accepted IPC actions: {"action": "dump_config"}, {"action": "set_worker", "path": "<file_path>"}.
[2026-09-18 10:00:03] [AUDIT_CHECKPOINT] FLAG{CHAIN_C_STEP1_AUDIT_LOG_LEAK_5519}
[2026-09-18 10:00:05] [INFO] Maintenance root daemon worker initialized at /usr/local/bin/default_worker.sh.
EOF
chmod 644 /var/log/audit/sysdaemon.log

# Create default worker
cat << 'EOF' > /usr/local/bin/default_worker.sh
#!/bin/bash
echo "[$(date)] Default maintenance worker check complete."
EOF
chmod 755 /usr/local/bin/default_worker.sh

# Create root flag
echo "FLAG{CHAIN_C_STEP3_LOCAL_ROOT_TAKEOVER_9981}" > /root/flag.txt
chmod 600 /root/flag.txt

# Start background local daemon (port 9090)
python3 /app/local_daemon.py &

# Start background root maintenance cron loop
bash /app/maintenance_cron.sh &

# Start web terminal
exec python3 /app/web_terminal.py
