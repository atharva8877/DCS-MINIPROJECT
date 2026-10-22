from flask import Flask, render_template, request, jsonify
import time
import threading
import requests
import uuid

app = Flask(__name__)

workers = {}
tasks_history = []
workers_lock = threading.Lock()
tasks_lock = threading.Lock()

TIMEOUT_THRESHOLD = 10

def background_health_checker():
    while True:
        time.sleep(3)
        current_time = time.time()
        with workers_lock:
            dead_workers = [wid for wid, data in workers.items() if current_time - data["last_seen"] > TIMEOUT_THRESHOLD]
            for wid in dead_workers:
                print(f"[Coordinator] Worker {wid} timed out (Dead).")
                del workers[wid]

threading.Thread(target=background_health_checker, daemon=True).start()

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/register", methods=["POST"])
def register_worker():
    data = request.json
    worker_id = data.get("worker_id")
    port = data.get("port")
    with workers_lock:
        workers[worker_id] = {"port": port, "cpu": 0.0, "ram": 0.0, "last_seen": time.time()}
    print(f"[Coordinator] Registered: {worker_id} on port {port}")
    return jsonify({"status": "success"}), 200

@app.route("/heartbeat", methods=["POST"])
def receive_heartbeat():
    data = request.json
    worker_id = data.get("worker_id")
    with workers_lock:
        if worker_id in workers:
            workers[worker_id]["cpu"] = data.get("cpu", 0.0)
            workers[worker_id]["ram"] = data.get("ram", 0.0)
            workers[worker_id]["last_seen"] = time.time()
    return jsonify({"status": "healthy"}), 200

@app.route("/api/workers", methods=["GET"])
def get_workers():
    with workers_lock:
        current_time = time.time()
        return jsonify([{
            "worker_id": wid,
            "port": d["port"],
            "cpu": d["cpu"],
            "ram": d["ram"],
            "status": "Alive" if current_time - d["last_seen"] <= TIMEOUT_THRESHOLD else "Dead"
        } for wid, d in workers.items()])

@app.route("/api/submit_task", methods=["POST"])
def submit_task():
    """Load balancer logic: routes task to the worker with the lowest CPU load."""
    data = request.json
    task_data = data.get("data", "Sample Task")
    task_id = str(uuid.uuid4())[:8]

    with workers_lock:
        current_time = time.time()
        alive_workers = {wid: d for wid, d in workers.items() if current_time - d["last_seen"] <= TIMEOUT_THRESHOLD}

    if not alive_workers:
        return jsonify({"status": "error", "message": "No active worker nodes available!"}), 503

    # Load Balancing Algorithm: Least CPU Utilization
    best_worker_id = min(alive_workers, key=lambda wid: alive_workers[wid]["cpu"])
    worker_port = alive_workers[best_worker_id]["port"]

    print(f"[LoadBalancer] Routing Task {task_id} to {best_worker_id} (Port {worker_port})")

    # Forward task to selected worker node
    try:
        res = requests.post(f"http://127.0.0.1:{worker_port}/execute", json={"task_id": task_id, "data": task_data}, timeout=5)
        result_data = res.json().get("result", "Completed")
    except Exception as e:
        result_data = f"Failed to execute: {e}"

    task_record = {"task_id": task_id, "worker": best_worker_id, "data": task_data, "result": result_data, "status": "Completed"}
    
    with tasks_lock:
        tasks_history.insert(0, task_record)

    return jsonify({"status": "success", "task": task_record}), 200

@app.route("/api/tasks", methods=["GET"])
def get_tasks():
    with tasks_lock:
        return jsonify(tasks_history)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)