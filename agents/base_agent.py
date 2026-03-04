"""
base_agent.py
Abstract base for all agents. Zero external dependencies.
"""

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class BaseAgent(ABC):
    def __init__(self, name: str, goal_id: str = None):
        self.name    = name
        self.goal_id = goal_id
        self.logger  = logging.getLogger(name)
        self._attach_file_handler()

    def _attach_file_handler(self) -> None:
        log_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(log_dir, exist_ok=True)
        if not any(isinstance(h, logging.FileHandler) for h in self.logger.handlers):
            fh = logging.FileHandler(os.path.join(log_dir, f"{self.name}.log"))
            fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
            self.logger.addHandler(fh)
        self.logger.setLevel(logging.DEBUG)

    def log(self, event_type: str, data: Dict[str, Any],
            task_id: str = None, status: str = "info") -> None:
        from memory.memory_store import log_event
        self.logger.info(f"[{event_type}] {data}")
        log_event(event_type, self.name, data, goal_id=self.goal_id,
                  task_id=task_id, status=status)

    def success(self, result: Any) -> Dict:
        return {"status": "success", "agent": self.name, "result": result}

    def failure(self, reason: str) -> Dict:
        self.log("failure", {"reason": reason}, status="error")
        return {"status": "failure", "agent": self.name, "reason": reason}

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        pass
