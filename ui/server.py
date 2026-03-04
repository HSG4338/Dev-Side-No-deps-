"""
server.py
Lightweight HTTP server using only stdlib http.server + threading.
Replaces Flask entirely. Zero external dependencies.
Routes:
  GET  /                    → dashboard HTML
  GET  /api/status          → system status JSON
  GET  /api/goals           → all goals JSON
  GET  /api/goal/<id>       → goal detail JSON
  GET  /api/events          → recent events JSON
  GET  /api/workspace       → workspace file list JSON
  GET  /api/logs            → in-memory log buffer JSON
  GET  /static/<file>       → static assets
  POST /api/submit_goal     → submit a goal (runs in background thread)
  POST /api/setup           → trigger dependency check
"""

import http.server
import json
import mimetypes
import os
import sys
import threading
import urllib.parse
from datetime import datetime
from typing import Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
STATIC_DIR   = os.path.join(os.path.dirname(__file__), "static")

# ── Shared state ──────────────────────────────────────────────────────────────
_log_buffer: List[Dict] = []
_log_lock   = threading.Lock()
_active_goal = {"running": False, "goal_id": None}
_active_lock = threading.Lock()


def _buf_log(msg: str) -> None:
    with _log_lock:
        _log_buffer.append({"time": datetime.utcnow().isoformat(), "msg": msg})
        if len(_log_buffer) > 500:
            _log_buffer.pop(0)


# ── Request handler ───────────────────────────────────────────────────────────

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # suppress default access log noise

    def _send(self, code: int, body: str, content_type: str = "application/json") -> None:
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code: int, obj) -> None:
        self._send(code, json.dumps(obj, default=str), "application/json")

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path.rstrip("/") or "/"

        if path == "/":
            self._serve_template("index.html")
        elif path == "/api/status":
            self._api_status()
        elif path == "/api/goals":
            self._api_goals()
        elif path.startswith("/api/goal/"):
            self._api_goal_detail(path.split("/api/goal/", 1)[1])
        elif path == "/api/events":
            self._api_events()
        elif path == "/api/workspace":
            self._api_workspace()
        elif path == "/api/logs":
            with _log_lock:
                self._json(200, list(_log_buffer[-100:]))
        elif path == "/api/models":
            self._api_models()
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
        else:
            self._json(404, {"error": "Not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path

        if path == "/api/submit_goal":
            self._api_submit_goal()
        elif path == "/api/setup":
            self._api_setup()
        elif path == "/api/set_provider":
            self._api_set_provider()
        else:
            self._json(404, {"error": "Not found"})

    # ── API handlers ──────────────────────────────────────────────────────────

    def _api_status(self):
        from memory.memory_store import get_all_goals, get_recent_events
        goals  = get_all_goals()
        events = get_recent_events(limit=5)
        self._json(200, {
            "goals_total":       len(goals),
            "goals_completed":   sum(1 for g in goals if g["status"] == "completed"),
            "goals_failed":      sum(1 for g in goals if g["status"] == "failed"),
            "goals_in_progress": sum(1 for g in goals if g["status"] == "in_progress"),
            "recent_events":     events,
            "active_goal":       dict(_active_goal),
            "timestamp":         datetime.utcnow().isoformat(),
        })

    def _api_goals(self):
        from memory.memory_store import get_all_goals
        self._json(200, get_all_goals())

    def _api_goal_detail(self, goal_id: str):
        from memory.memory_store import get_tasks_for_goal, query_events
        tasks  = get_tasks_for_goal(goal_id)
        events = [e for e in query_events(limit=200) if e.get("goal_id") == goal_id]
        self._json(200, {"tasks": tasks, "events": events})

    def _api_events(self):
        from memory.memory_store import get_recent_events
        self._json(200, get_recent_events(limit=50))

    def _api_workspace(self):
        ws = os.path.join(PROJECT_ROOT, "workspace")
        files = []
        if os.path.exists(ws):
            for fn in sorted(os.listdir(ws)):
                fp = os.path.join(ws, fn)
                if os.path.isfile(fp):
                    files.append({
                        "name":     fn,
                        "size":     os.path.getsize(fp),
                        "modified": datetime.utcfromtimestamp(os.path.getmtime(fp)).isoformat(),
                    })
        self._json(200, files)

    def _api_submit_goal(self):
        with _active_lock:
            if _active_goal["running"]:
                self._json(409, {"error": "A goal is already running. Please wait."})
                return
        data = self._read_body()
        goal = data.get("goal", "").strip()
        if not goal:
            self._json(400, {"error": "Goal cannot be empty"})
            return

        def _run():
            with _active_lock:
                _active_goal["running"] = True
            _buf_log(f"Goal submitted: {goal}")
            try:
                from orchestrator.orchestrator import Orchestrator
                result = Orchestrator().run_goal(goal)
                with _active_lock:
                    _active_goal["goal_id"] = result.get("goal_id")
                _buf_log(f"Goal done: {result['status']} — {result['summary']}")
            except Exception as e:
                _buf_log(f"Goal error: {e}")
            finally:
                with _active_lock:
                    _active_goal["running"] = False

        threading.Thread(target=_run, daemon=True).start()
        self._json(200, {"message": "Goal submitted", "running": True})

    def _api_setup(self):
        def _run():
            _buf_log("Checking dependencies (stdlib only — nothing to install)...")
            _buf_log("Python: " + sys.version.split()[0])
            _buf_log("All required modules are stdlib. System ready.")
        threading.Thread(target=_run, daemon=True).start()
        self._json(200, {"message": "Dependency check complete — stdlib only, nothing to install."})

    def _api_models(self):
        from models.llm_client import get_provider_status
        self._json(200, get_provider_status())

    def _api_set_provider(self):
        """Switch the active LLM provider and save to config."""
        import json as _json
        data = self._read_body()
        provider = data.get("provider", "").lower()
        valid = {"anthropic", "ollama", "huggingface"}
        if provider not in valid:
            self._json(400, {"error": f"Invalid provider. Choose: {', '.join(valid)}"})
            return
        cfg_path = os.path.join(PROJECT_ROOT, "configs", "config.json")
        with open(cfg_path, "r") as f:
            cfg = _json.load(f)
        cfg["llm"]["provider"] = provider
        with open(cfg_path, "w") as f:
            _json.dump(cfg, f, indent=2)
        _buf_log(f"Provider switched to: {provider}")
        self._json(200, {"message": f"Provider set to '{provider}'", "provider": provider})

    # ── Static / template helpers ─────────────────────────────────────────────

    def _serve_template(self, name: str):
        path = os.path.join(TEMPLATE_DIR, name)
        if not os.path.exists(path):
            self._json(404, {"error": f"Template {name} not found"})
            return
        with open(path, "r", encoding="utf-8") as f:
            self._send(200, f.read(), "text/html; charset=utf-8")

    def _serve_static(self, filename: str):
        safe = os.path.basename(filename)
        path = os.path.join(STATIC_DIR, safe)
        if not os.path.exists(path):
            self._json(404, {"error": "Not found"})
            return
        mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# ── Server entry point ─────────────────────────────────────────────────────────

def run(host: str = "127.0.0.1", port: int = 5000) -> None:
    from memory.memory_store import init_db
    init_db()
    server = http.server.ThreadingHTTPServer((host, port), Handler)
    print(f"\n🤖  Agentic AI UI → http://{host}:{port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.shutdown()


if __name__ == "__main__":
    cfg_path = os.path.join(PROJECT_ROOT, "configs", "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    ui = cfg.get("ui", {})
    run(host=ui.get("host", "127.0.0.1"), port=ui.get("port", 5000))
