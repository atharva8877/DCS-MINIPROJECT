import time
import requests
import psutil
import sys
import threading
from flask import Flask, jsonify, request

# Configuration
COORDINATOR_URL = "http://127.0.0.1:5000"
WORKER_PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
WORKER_ID = f"worker-{WORKER_PORT}"
app = Flask(__name__)


@app.route("/execute", methods=["POST"])
def execute_task():
    task = request.get_json()
    if not task or "task_id" not in task or "data" not in task:
        return jsonify({"status": "error", "message": "task_id and data are required"}), 400

    print(f"[{WORKER_ID}] Executed task {task['task_id']}: {task['data']}")
    return jsonify({"status": "success", "result": f"Processed: {task['data']}"})

def register_worker():
    """Register this worker node with the central coordinator."""
    url = f"{COORDINATOR_URL}/register"
    payload = {
        "worker_id": WORKER_ID,
        "port": WORKER_PORT
    }
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(f"[{WORKER_ID}] Successfully registered with coordinator.")
        else:
            print(f"[{WORKER_ID}] Failed to register. Status: {response.status_code}")
    except Exception as e:
        print(f"[{WORKER_ID}] Error connecting to coordinator: {e}")

def send_heartbeat():
    """Continuously send heartbeat and metrics to the coordinator."""
    url = f"{COORDINATOR_URL}/heartbeat"
    while True:
        try:
            cpu_usage = psutil.cpu_percent(interval=1)
            ram_usage = psutil.virtual_memory().percent
            
            payload = {
                "worker_id": WORKER_ID,
                "cpu": cpu_usage,
                "ram": ram_usage
            }
            
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print(f"[{WORKER_ID}] Heartbeat sent -> CPU: {cpu_usage}%, RAM: {ram_usage}%")
            else:
                print(f"[{WORKER_ID}] Heartbeat rejected. Status: {response.status_code}")
        except Exception as e:
            print(f"[{WORKER_ID}] Coordinator offline or unreachable: {e}")
        
        time.sleep(3) # Send heartbeat every 3 seconds

if __name__ == "__main__":
    print(f"Starting {WORKER_ID} on port {WORKER_PORT}...")
    time.sleep(2) # Give coordinator a moment to start if launched together
    register_worker()
    threading.Thread(target=send_heartbeat, daemon=True).start()
    app.run(host="0.0.0.0", port=WORKER_PORT)