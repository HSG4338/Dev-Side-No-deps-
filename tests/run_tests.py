"""
run_tests.py
Stdlib-only test runner. Discovers and runs all test_*.py files in tests/ and workspace/.
Usage: python tests/run_tests.py
"""

import os
import sys
import unittest

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "workspace"))

def run_all() -> bool:
    loader  = unittest.TestLoader()
    suite   = unittest.TestSuite()

    # Discover tests in tests/
    tests_dir = os.path.dirname(__file__)
    suite.addTests(loader.discover(tests_dir, pattern="test_*.py"))

    # Discover tests in workspace/
    ws_dir = os.path.join(PROJECT_ROOT, "workspace")
    if os.path.exists(ws_dir):
        suite.addTests(loader.discover(ws_dir, pattern="test_*.py"))

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
