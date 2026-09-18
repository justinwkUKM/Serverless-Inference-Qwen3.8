#!/bin/bash
# Periodic root maintenance task
while true; do
    if [ -f "/var/run/worker_config.json" ]; then
        WORKER=$(grep -o '"active_worker": "[^"]*' /var/run/worker_config.json | cut -d'"' -f4)
        if [ -n "$WORKER" ] && [ -x "$WORKER" ]; then
            # Executes the active worker with root privileges
            "$WORKER" > /tmp/worker_last_run.log 2>&1
        fi
    fi
    sleep 5
done
