"""
developer_agent.py
Writes Python files to /workspace only. Zero external dependencies.
"""

import os
import re
import textwrap
from typing import Any, Dict

from agents.base_agent import BaseAgent

PROJECT_ROOT   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, "workspace")

SYSTEM_PROMPT = """You are a Python developer. Write complete, runnable Python code.
Rules:
- Output ONLY the file content. No markdown fences, no explanation.
- Use only Python standard library.
- Include docstrings, type hints, error handling, and a main() guard.
- Code must be immediately runnable."""


class DeveloperAgent(BaseAgent):
    def __init__(self, goal_id: str = None):
        super().__init__("DeveloperAgent", goal_id=goal_id)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        task        = context.get("task", {})
        description = task.get("description", "")
        goal        = context.get("goal", "")
        filename    = context.get("filename") or self._infer_filename(description)
        prev        = context.get("previous_code", "")

        if not description:
            return self.failure("No task description")

        self.log("dev_start", {"description": description, "file": filename})
        revision = f"\n\nPrevious attempt needing revision:\n{prev}" if prev else ""

        try:
            from models.llm_client import generate
            code = generate(
                agent_role="developer",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"Goal: {goal}\nTask: {description}\nWrite the complete file {filename}:{revision}\n",
                goal=goal,
                description=description,
                filename=filename,
                previous_code=prev,
            )
            code = self._clean(code)
            if len(code.strip()) < 10:
                raise ValueError("Generated code too short")
        except Exception as e:
            self.logger.warning(f"Dev LLM failed: {e}, using stub")
            code = self._stub(description, goal)

        try:
            filepath = self._write(filename, code)
        except Exception as e:
            return self.failure(str(e))

        self.log("dev_complete", {"file": filepath, "lines": len(code.splitlines())})
        return self.success({"file": filepath, "code": code, "filename": filename})

    def _infer_filename(self, description: str) -> str:
        words = re.findall(r'[a-z]+', description.lower())
        name  = "_".join(words[:3]) if words else "module"
        return f"{name}.py"

    def _clean(self, raw: str) -> str:
        raw = re.sub(r'^```(?:python)?\n?', '', raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r'\n?```$',           '', raw.strip(), flags=re.MULTILINE)
        return raw.strip()

    def _write(self, filename: str, code: str) -> str:
        os.makedirs(WORKSPACE_ROOT, exist_ok=True)
        # Block traversal BEFORE stripping — check raw input
        if ".." in filename or filename.startswith("/"):
            raise PermissionError(f"Path escape blocked: {filename}")
        safe     = os.path.basename(filename)
        abs_path = os.path.abspath(os.path.join(WORKSPACE_ROOT, safe))
        if not abs_path.startswith(os.path.abspath(WORKSPACE_ROOT)):
            raise PermissionError(f"Path escape blocked: {filename}")
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(code)
        return abs_path

    def _stub(self, description: str, goal: str) -> str:
        return textwrap.dedent(f'''\
            """
            Auto-generated stub.
            Goal: {goal}
            Task: {description}
            """
            import sys


            def main():
                print("Stub: {description}")


            if __name__ == "__main__":
                main()
        ''')
