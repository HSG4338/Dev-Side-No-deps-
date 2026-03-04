"""
planner_agent.py
Decomposes goals into task graphs. Zero external dependencies.
"""

import json
import re
from typing import Any, Dict, List

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """You are a software project planner. Decompose the goal into concrete tasks.
Output ONLY valid JSON with this exact structure:
{"tasks": [{"id":"t1","description":"...","agent":"developer","depends_on":[]}, ...]}
agent must be one of: developer, reviewer, qa. Maximum 6 tasks. No prose outside JSON."""


class PlannerAgent(BaseAgent):
    def __init__(self, goal_id: str = None):
        super().__init__("PlannerAgent", goal_id=goal_id)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        goal = context.get("goal", "")
        if not goal:
            return self.failure("No goal provided")
        self.log("plan_start", {"goal": goal})
        try:
            from models.llm_client import generate
            raw = generate(
                agent_role="planner",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"Goal: {goal}\n\nOutput the task graph JSON:",
                goal=goal,
            )
            tasks = self._parse(raw, goal)
        except Exception as e:
            self.logger.warning(f"Planner LLM failed: {e}")
            tasks = self._fallback(goal)
        self.log("plan_complete", {"tasks": len(tasks)})
        return self.success({"tasks": tasks})

    def _parse(self, raw: str, goal: str) -> List[Dict]:
        # Find first JSON object containing "tasks"
        depth, start = 0, -1
        for i, ch in enumerate(raw):
            if ch == '{':
                if depth == 0: start = i
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0 and start != -1:
                    try:
                        data  = json.loads(raw[start:i+1])
                        tasks = data.get("tasks", [])
                        if tasks and isinstance(tasks, list):
                            validated = self._validate(tasks)
                            if validated:
                                return validated
                    except (json.JSONDecodeError, KeyError):
                        pass
                    start = -1
        return self._fallback(goal)

    def _validate(self, tasks: List[Dict]) -> List[Dict]:
        valid_agents = {"developer", "reviewer", "qa"}
        out = []
        for i, t in enumerate(tasks[:6]):
            if not isinstance(t, dict):
                continue
            out.append({
                "id": t.get("id", f"t{i+1}"),
                "description": str(t.get("description", f"Task {i+1}")),
                "agent": t.get("agent", "developer") if t.get("agent") in valid_agents else "developer",
                "depends_on": t.get("depends_on", []) if isinstance(t.get("depends_on"), list) else [],
            })
        return out

    def _fallback(self, goal: str) -> List[Dict]:
        return [
            {"id": "t1", "description": f"Implement: {goal}", "agent": "developer", "depends_on": []},
            {"id": "t2", "description": f"Write tests for: {goal}", "agent": "qa", "depends_on": ["t1"]},
            {"id": "t3", "description": f"Review implementation of: {goal}", "agent": "reviewer", "depends_on": ["t1"]},
        ]
