"""Tests for DeveloperAgent — stdlib unittest only."""
import os, sys, unittest
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from agents.developer_agent import DeveloperAgent, WORKSPACE_ROOT

class TestDeveloperAgent(unittest.TestCase):
    def setUp(self): self.d = DeveloperAgent()

    def test_infer_filename(self):
        name = self.d._infer_filename("Create a calculator for math")
        self.assertTrue(name.endswith(".py"))

    def test_clean_removes_fences(self):
        raw = "```python\ndef foo():\n    pass\n```"
        self.assertNotIn("```", self.d._clean(raw))
        self.assertIn("def foo", self.d._clean(raw))

    def test_clean_passthrough(self):
        raw = "def bar():\n    return 1"
        self.assertEqual(self.d._clean(raw), raw)

    def test_safe_write(self):
        path = self.d._write("_test_dev.py", "x=1\n")
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.startswith(WORKSPACE_ROOT))
        os.remove(path)

    def test_safe_write_blocks_traversal(self):
        with self.assertRaises(PermissionError):
            self.d._write("../../evil.py", "bad")

    def test_stub_has_main(self):
        stub = self.d._stub("Create X", "Build X")
        self.assertIn("def main", stub)
        self.assertIn("__main__", stub)

    def test_no_description_returns_failure(self):
        self.assertEqual(self.d.run({"task":{},"goal":"test"})["status"], "failure")

if __name__ == "__main__": unittest.main()
