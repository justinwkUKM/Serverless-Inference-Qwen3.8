import os
import json
import socket
import threading

DAEMON_CONFIG = {
    "active_worker": "/usr/local/bin/default_worker.sh",
    "status": "idle",
    "milestone_token": "FLAG{CHAIN_C_STEP2_LOCAL_IPC_HIJACK_6628}"
}

CONFIG_FILE = "/var/run/worker_config.json"

def save_config():
    with open(CONFIG_FILE, "w") as f:
        json.dump(DAEMON_CONFIG, f)

def handle_client(conn):
    try:
        data = conn.recv(1024).decode("utf-8")
        if not data:
            return
        cmd = json.loads(data)
        action = cmd.get("action")
        if action == "dump_config":
            resp = json.dumps(DAEMON_CONFIG)
        elif action == "set_worker":
            new_path = cmd.get("path")
            if new_path:
                DAEMON_CONFIG["active_worker"] = new_path
                save_config()
                resp = json.dumps({"status": "success", "worker": new_path})
            else:
                resp = json.dumps({"error": "Missing path"})
        else:
            resp = json.dumps({"error": "Unknown action"})
        conn.sendall((resp + "\n").encode("utf-8"))
    except Exception as e:
        conn.sendall((json.dumps({"error": str(e)}) + "\n").encode("utf-8"))
    finally:
        conn.close()

def main():
    save_config()
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Listens strictly on localhost loopback
    server.bind(("127.0.0.1", 9090))
    server.listen(5)
    while True:
        conn, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(conn,))
        t.start()

if __name__ == "__main__":
    main()
