"""
repo_manager_agent.py
Filesystem permission enforcement and workspace management. Zero external deps.
"""

import hashlib
import os
import shutil
from datetime import datetime
from typing import Any, Dict

from agents.base_agent import BaseAgent

PROJECT_ROOT   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_ROOT = os.path.abspath(os.path.join(PROJECT_ROOT, "workspace"))
FORBIDDEN      = [
    os.path.join(PROJECT_ROOT, d)
    for d in ("models", "memory", "logs", "configs", "agents", "orchestrator", "ui")
]


class RepoManagerAgent(BaseAgent):
    def __init__(self, goal_id: str = None):
        super().__init__("RepoManagerAgent", goal_id=goal_id)
        os.makedirs(WORKSPACE_ROOT, exist_ok=True)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        action = context.get("action", "commit")
        if action == "commit":   return self._commit(context)
        if action == "list":     return self._list()
        if action == "delete":   return self._delete(context)
        if action == "snapshot": return self._snapshot()
        return self.failure(f"Unknown action: {action}")

    def _commit(self, context: Dict) -> Dict:
        filepath = context.get("file", "")
        if not filepath:
            return self.failure("No file path provided")
        abs_path = os.path.abspath(filepath)
        violation = self._check(abs_path)
        if violation:
            self.log("permission_violation", {"path": abs_path, "reason": violation}, status="error")
            try: os.remove(abs_path)
            except Exception: pass
            return self.failure(f"Permission violation: {violation}")
        if not os.path.exists(abs_path):
            return self.failure(f"File not found: {abs_path}")
        chk  = self._checksum(abs_path)
        size = os.path.getsize(abs_path)
        self.log("file_committed", {"path": abs_path, "checksum": chk, "size": size})
        return self.success({"file": abs_path, "checksum": chk, "size": size})

    def _list(self) -> Dict:
        files = []
        for root, _, fns in os.walk(WORKSPACE_ROOT):
            for fn in fns:
                fp = os.path.join(root, fn)
                files.append({"path": fp, "size": os.path.getsize(fp),
                               "modified": datetime.utcfromtimestamp(os.path.getmtime(fp)).isoformat()})
        return self.success({"files": files})

    def _delete(self, context: Dict) -> Dict:
        abs_path = os.path.abspath(context.get("file", ""))
        if self._check(abs_path):
            return self.failure(f"Cannot delete outside workspace")
        if os.path.exists(abs_path):
            os.remove(abs_path)
            self.log("file_deleted", {"path": abs_path})
            return self.success({"deleted": abs_path})
        return self.failure(f"Not found: {abs_path}")

    def _snapshot(self) -> Dict:
        name    = f"snapshot_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        snap_dir = os.path.join(PROJECT_ROOT, "logs", "snapshots", name)
        os.makedirs(snap_dir, exist_ok=True)
        copied = 0
        for root, _, fns in os.walk(WORKSPACE_ROOT):
            for fn in fns:
                shutil.copy2(os.path.join(root, fn), os.path.join(snap_dir, fn))
                copied += 1
        self.log("snapshot_created", {"dir": snap_dir, "files": copied})
        return self.success({"snapshot": snap_dir, "files_copied": copied})

    def _check(self, abs_path: str) -> str:
        if not abs_path.startswith(WORKSPACE_ROOT):
            for fp in FORBIDDEN:
                if abs_path.startswith(fp):
                    return f"Forbidden zone: {fp}"
            return f"Outside workspace: {abs_path}"
        return ""

    def _checksum(self, path: str) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:12]

    def is_allowed(self, filepath: str) -> bool:
        return self._check(os.path.abspath(filepath)) == ""
