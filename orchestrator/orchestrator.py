"""
orchestrator.py
Central goal execution loop. Zero external dependencies.
"""

import json
import logging
import os
import sys
import time
import uuid
from typing import Any, Dict, List

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from agents import PlannerAgent, DeveloperAgent, ReviewerAgent, QAAgent, RepoManagerAgent
from memory.memory_store import create_goal, update_goal, create_task, update_task, log_event

LOG_DIR    = os.path.join(PROJECT_ROOT, "logs")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "configs", "config.json")


def _setup_logging() -> logging.Logger:
    os.makedirs(LOG_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join(LOG_DIR, "orchestrator.log")),
        ],
    )
    return logging.getLogger("Orchestrator")


def _cfg() -> dict:
    with open(CONFIG_PATH) as f:
        return json.load(f)


class Orchestrator:
    def __init__(self):
        self.logger      = _setup_logging()
        self.cfg         = _cfg()
        self.max_retries = self.cfg["system"]["max_retries"]
        self.logger.info("Orchestrator ready")

    def run_goal(self, goal: str) -> Dict[str, Any]:
        goal_id = str(uuid.uuid4())[:8]
        self.logger.info(f"[{goal_id}] Goal: {goal}")
        create_goal(goal_id, goal)
        log_event("goal_received", "Orchestrator", {"goal": goal}, goal_id=goal_id)

        # ── Plan ──────────────────────────────────────────────────────────
        plan = self._retry(PlannerAgent(goal_id=goal_id).run, {"goal": goal}, goal_id, "plan")
        if plan["status"] == "failure":
            update_goal(goal_id, status="failed", result="Planning failed")
            return self._fail(goal_id, "Planning failed")

        tasks: List[Dict] = plan["result"]["tasks"]
        self.logger.info(f"[{goal_id}] {len(tasks)} tasks planned")
        update_goal(goal_id, status="in_progress")

        for t in tasks:
            create_task(f"{goal_id}_{t['id']}", goal_id, t["description"], agent=t["agent"])

        # ── Execute each task ─────────────────────────────────────────────
        summaries, all_ok = [], True
        for task in tasks:
            s = self._exec_task(task, goal_id, goal)
            summaries.append(s)
            if s["status"] == "failure":
                all_ok = False

        # ── Snapshot ──────────────────────────────────────────────────────
        RepoManagerAgent(goal_id=goal_id).run({"action": "snapshot"})

        ok_count     = sum(1 for s in summaries if s["status"] == "success")
        final_status = "completed" if all_ok else "partial"
        summary_text = f"{ok_count}/{len(tasks)} tasks succeeded"
        update_goal(goal_id, status=final_status, result=summary_text)
        log_event("goal_finished", "Orchestrator",
                  {"status": final_status, "summary": summary_text}, goal_id=goal_id)
        self.logger.info(f"[{goal_id}] {final_status}: {summary_text}")
        return {"goal_id": goal_id, "status": final_status, "summary": summary_text, "tasks": summaries}

    def _exec_task(self, task: Dict, goal_id: str, goal: str) -> Dict:
        task_id    = f"{goal_id}_{task['id']}"
        agent_type = task.get("agent", "developer")
        update_task(task_id, status="in_progress")

        if agent_type not in ("developer", "qa"):
            update_task(task_id, status="completed")
            return {"task_id": task_id, "status": "success"}

        # ── Developer ─────────────────────────────────────────────────────
        dev = DeveloperAgent(goal_id=goal_id)
        dev_ctx = {"goal": goal, "task": task}
        dev_res = self._retry(dev.run, dev_ctx, goal_id, f"dev_{task_id}")
        if dev_res["status"] == "failure":
            update_task(task_id, status="failed", result=dev_res.get("reason"))
            return {"task_id": task_id, "status": "failure", "reason": "Developer failed"}

        code     = dev_res["result"]["code"]
        filename = dev_res["result"]["filename"]
        filepath = dev_res["result"]["file"]

        # ── Reviewer (up to max_retries) ──────────────────────────────────
        verdict = "reject"
        for attempt in range(self.max_retries):
            rev_res = self._retry(ReviewerAgent(goal_id=goal_id).run,
                                  {"code": code, "filename": filename, "file": filepath},
                                  goal_id, f"rev_{task_id}")
            if rev_res["status"] == "failure":
                break
            verdict = rev_res["result"].get("verdict", "approve")
            if verdict == "approve":
                break
            # Revise
            suggestions = rev_res["result"].get("suggestions", "")
            revised_task = dict(task)
            revised_task["description"] += f" [REVISE: {suggestions}]"
            dev_ctx2 = {"goal": goal, "task": revised_task, "previous_code": code}
            dev_res2 = self._retry(dev.run, dev_ctx2, goal_id, f"dev_rev_{task_id}_{attempt}")
            if dev_res2["status"] == "success":
                code     = dev_res2["result"]["code"]
                filepath = dev_res2["result"]["file"]

        # ── QA ────────────────────────────────────────────────────────────
        qa_res      = self._retry(QAAgent(goal_id=goal_id).run,
                                  {"code": code, "filename": filename, "file": filepath, "goal": goal},
                                  goal_id, f"qa_{task_id}")
        tests_passed = qa_res["status"] == "success" and qa_res["result"].get("passed", False)

        # ── Commit ────────────────────────────────────────────────────────
        RepoManagerAgent(goal_id=goal_id).run({"action": "commit", "file": filepath})
        update_task(task_id, status="completed",
                    result={"verdict": verdict, "tests_passed": tests_passed, "file": filepath})

        return {"task_id": task_id, "status": "success", "file": filepath,
                "verdict": verdict, "tests_passed": tests_passed,
                "qa_output": qa_res.get("result", {}).get("output", "")}

    def _retry(self, fn, ctx: Dict, goal_id: str, stage: str) -> Dict:
        last = {"status": "failure", "reason": "No attempts"}
        for i in range(1, self.max_retries + 1):
            try:
                r = fn(ctx)
                if r.get("status") == "success":
                    return r
                last = r
            except Exception as e:
                self.logger.error(f"[{goal_id}] {stage} attempt {i}: {e}")
                last = {"status": "failure", "reason": str(e)}
            time.sleep(0.3 * i)
        return last

    def _fail(self, goal_id: str, reason: str) -> Dict:
        log_event("goal_failed", "Orchestrator", {"reason": reason}, goal_id=goal_id, status="error")
        return {"goal_id": goal_id, "status": "failed", "summary": reason, "tasks": []}
