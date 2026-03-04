"""
reviewer_agent.py
Reviews code with AST static analysis + optional LLM. Zero external deps.
"""

import ast
import json
import os
import re
from typing import Any, Dict

from agents.base_agent import BaseAgent

SYSTEM_PROMPT = """You are a strict Python code reviewer.
Respond ONLY with JSON: {"verdict":"approve"|"reject","issues":["..."],"suggestions":"..."}
Check for: syntax errors, undefined variables, missing error handling, path traversal, security issues."""


class ReviewerAgent(BaseAgent):
    def __init__(self, goal_id: str = None):
        super().__init__("ReviewerAgent", goal_id=goal_id)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code     = context.get("code", "")
        filename = context.get("filename", "unknown.py")
        filepath = context.get("file", "")

        if not code and filepath and os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
        if not code:
            return self.failure("No code to review")

        self.log("review_start", {"filename": filename})
        static_issues = self._static(code)

        # Try LLM review
        verdict, issues, suggestions = "approve", static_issues, ""
        try:
            from models.llm_client import generate
            raw = generate(
                agent_role="reviewer",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"File: {filename}\n\n{code}\n\nJSON review:",
                code=code,
                filename=filename,
            )
            m = re.search(r'\{[\s\S]*?"verdict"[\s\S]*?\}', raw)
            if m:
                rev = json.loads(m.group(0))
                verdict    = rev.get("verdict", "approve")
                issues     = list(rev.get("issues", [])) + static_issues
                suggestions = rev.get("suggestions", "")
        except Exception as e:
            self.logger.warning(f"Reviewer LLM failed: {e}")
            verdict = "reject" if static_issues else "approve"
            issues  = static_issues
            suggestions = "; ".join(static_issues)

        if verdict == "approve" and not static_issues:
            self.log("review_approved", {"filename": filename})
        else:
            verdict = "reject" if (issues or static_issues) else "approve"
            self.log("review_rejected", {"filename": filename, "issues": issues}, status="warning")

        return self.success({
            "verdict": verdict, "issues": issues,
            "suggestions": suggestions, "filename": filename,
        })

    def _static(self, code: str) -> list:
        issues = []
        try:
            ast.parse(code)
        except SyntaxError as e:
            issues.append(f"SyntaxError line {e.lineno}: {e.msg}")
        if "../" in code or "..\\" in code:
            issues.append("Potential path traversal")
        if "os.system(" in code:
            issues.append("Unsafe os.system() call")
        return issues
