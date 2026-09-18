#!/bin/bash
# Periodic root maintenance task
while true; do
    if [ -f "/var/run/worker_config.json" ]; then
        WORKER=$(python3 -c "import json; print(json.load(open('/var/run/worker_config.json')).get('active_worker', ''))" 2>/dev/null)
        if [ -n "$WORKER" ] && [ -x "$WORKER" ]; then
            # Executes the active worker with root privileges
            "$WORKER" > /tmp/worker_last_run.log 2>&1
        fi
    fi
    sleep 3
done
