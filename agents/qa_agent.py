"""
qa_agent.py
Generates test files and runs them via stdlib unittest. No pytest needed.
Falls back gracefully if tests cannot run.
"""

import importlib
import importlib.util
import os
import re
import subprocess
import sys
import textwrap
from typing import Any, Dict

from agents.base_agent import BaseAgent

PROJECT_ROOT   = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
WORKSPACE_ROOT = os.path.join(PROJECT_ROOT, "workspace")

SYSTEM_PROMPT = """You are a Python test engineer. Write tests using the standard unittest module.
Rules:
- Output ONLY the test file content. No fences, no explanation.
- Use: import unittest
- Class must be named Test<ModuleName>(unittest.TestCase)
- Import target module with: sys.path.insert(0, os.path.dirname(__file__))
- Add: if __name__ == '__main__': unittest.main()"""


class QAAgent(BaseAgent):
    def __init__(self, goal_id: str = None):
        super().__init__("QAAgent", goal_id=goal_id)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        code     = context.get("code", "")
        filename = context.get("filename", "module.py")
        filepath = context.get("file", "")
        goal     = context.get("goal", "")

        if not code and filepath and os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                code = f.read()
        if not code:
            return self.failure("No code provided")

        module_name  = os.path.splitext(os.path.basename(filename))[0]
        test_filename = f"test_{module_name}.py"
        test_filepath = os.path.join(WORKSPACE_ROOT, test_filename)

        self.log("qa_start", {"module": module_name})

        # Generate test code
        try:
            from models.llm_client import generate
            test_code = generate(
                agent_role="qa",
                system_prompt=SYSTEM_PROMPT,
                user_prompt=f"Module: {module_name}\nGoal: {goal}\n\nCode:\n{code}\n\nWrite tests:",
                goal=goal,
                module_name=module_name,
                code=code,
            )
            test_code = self._clean(test_code)
            if "import unittest" not in test_code or len(test_code) < 30:
                raise ValueError("Bad test output")
        except Exception as e:
            self.logger.warning(f"QA LLM failed: {e}, using default tests")
            test_code = self._default_tests(module_name, code)

        os.makedirs(WORKSPACE_ROOT, exist_ok=True)
        with open(test_filepath, "w", encoding="utf-8") as f:
            f.write(test_code)

        result = self._run(test_filepath, module_name)
        self.log("qa_complete", result, status="success" if result["passed"] else "error")
        return self.success(result)

    def _clean(self, raw: str) -> str:
        raw = re.sub(r'^```(?:python)?\n?', '', raw.strip(), flags=re.MULTILINE)
        raw = re.sub(r'\n?```$',           '', raw.strip(), flags=re.MULTILINE)
        return raw.strip()

    def _run(self, test_filepath: str, module_name: str) -> Dict:
        try:
            proc = subprocess.run(
                [sys.executable, "-m", "unittest", test_filepath, "-v"],
                capture_output=True, text=True,
                cwd=WORKSPACE_ROOT, timeout=30,
            )
            output = proc.stdout + proc.stderr
            passed_count = output.count("ok")
            failed_count = output.count("FAIL") + output.count("ERROR")
            return {
                "passed":        proc.returncode == 0,
                "test_file":     test_filepath,
                "module":        module_name,
                "passed_count":  passed_count,
                "failed_count":  failed_count,
                "output":        output[-2000:],
                "returncode":    proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"passed": False, "test_file": test_filepath, "module": module_name,
                    "passed_count": 0, "failed_count": 1, "output": "Timed out", "returncode": -1}
        except Exception as e:
            return {"passed": False, "test_file": test_filepath, "module": module_name,
                    "passed_count": 0, "failed_count": 1, "output": str(e), "returncode": -1}

    def _default_tests(self, module_name: str, code: str) -> str:
        has_calc = all(f in code for f in ["def add", "def subtract", "def multiply", "def divide"])
        has_todo = all(f in code for f in ["def add_task", "def remove_task", "def list_tasks"])
        class_name = "".join(w.capitalize() for w in module_name.split("_"))

        if has_calc:
            return textwrap.dedent(f'''\
                import sys, os, unittest
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import {module_name}

                class Test{class_name}(unittest.TestCase):
                    def test_add(self):
                        self.assertEqual({module_name}.add(3, 5), 8)
                    def test_subtract(self):
                        self.assertEqual({module_name}.subtract(10, 4), 6)
                    def test_multiply(self):
                        self.assertEqual({module_name}.multiply(6, 7), 42)
                    def test_divide(self):
                        self.assertAlmostEqual({module_name}.divide(10, 2), 5.0)
                    def test_divide_by_zero(self):
                        with self.assertRaises((ValueError, ZeroDivisionError)):
                            {module_name}.divide(1, 0)
                    def test_calculate_add(self):
                        self.assertEqual({module_name}.calculate("add", 2, 3), 5)
                    def test_calculate_unknown(self):
                        with self.assertRaises((ValueError, KeyError)):
                            {module_name}.calculate("modulo", 5, 3)

                if __name__ == "__main__":
                    unittest.main()
            ''')

        if has_todo:
            return textwrap.dedent(f'''\
                import sys, os, unittest
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                import {module_name}

                class Test{class_name}(unittest.TestCase):
                    def test_add_task(self):
                        t = {module_name}.add_task("test task")
                        self.assertIn("id", t)
                        self.assertEqual(t["description"], "test task")
                    def test_list_tasks(self):
                        tasks = {module_name}.list_tasks()
                        self.assertIsInstance(tasks, list)
                    def test_remove_task(self):
                        t = {module_name}.add_task("to remove")
                        result = {module_name}.remove_task(t["id"])
                        self.assertTrue(result)

                if __name__ == "__main__":
                    unittest.main()
            ''')

        return textwrap.dedent(f'''\
            import sys, os, unittest, importlib
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

            class Test{class_name}(unittest.TestCase):
                def test_import(self):
                    mod = importlib.import_module("{module_name}")
                    self.assertIsNotNone(mod)
                def test_main_exists(self):
                    mod = importlib.import_module("{module_name}")
                    self.assertTrue(hasattr(mod, "main"))

            if __name__ == "__main__":
                unittest.main()
        ''')
