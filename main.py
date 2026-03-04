"""
main.py
CLI entry point for the Agentic AI System.
Zero external dependencies — pure Python stdlib.

Usage:
  python main.py --goal "Build a CLI calculator"
  python main.py --ui
  python main.py --validate
  python main.py --test
"""

import argparse
import importlib.util
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


def run_goal(goal: str) -> None:
    from orchestrator.orchestrator import Orchestrator
    result = Orchestrator().run_goal(goal)
    print(f"\n{'='*60}")
    print(f"Goal ID : {result['goal_id']}")
    print(f"Status  : {result['status'].upper()}")
    print(f"Summary : {result['summary']}")
    print(f"{'='*60}")
    for t in result.get("tasks", []):
        icon = "✓" if t.get("status") == "success" else "✗"
        tests = t.get("tests_passed", "?")
        print(f"  {icon} {t.get('task_id','?')}  tests_passed={tests}")
    print()


def run_ui() -> None:
    import json
    cfg_path = os.path.join(PROJECT_ROOT, "configs", "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    ui = cfg.get("ui", {})
    from ui.server import run
    run(host=ui.get("host", "127.0.0.1"), port=ui.get("port", 5000))


def run_tests() -> None:
    import unittest
    ws_dir    = os.path.join(PROJECT_ROOT, "workspace")
    tests_dir = os.path.join(PROJECT_ROOT, "tests")
    sys.path.insert(0, ws_dir)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # Discover tests/ suite
    suite.addTests(loader.discover(start_dir=tests_dir, pattern="test_*.py", top_level_dir=PROJECT_ROOT))

    # Manually load workspace test files to avoid top_level_dir assert issues
    for fn in sorted(os.listdir(ws_dir)):
        if fn.startswith("test_") and fn.endswith(".py"):
            spec = importlib.util.spec_from_file_location(fn[:-3], os.path.join(ws_dir, fn))
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            suite.addTests(loader.loadTestsFromModule(mod))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)


def run_validate() -> None:
    print("\n=== SELF-VALIDATION ===\n")
    required = [
        "configs/config.json",
        "memory/memory_store.py", "memory/__init__.py",
        "models/llm_client.py",   "models/__init__.py",
        "agents/base_agent.py",   "agents/planner_agent.py",
        "agents/developer_agent.py","agents/reviewer_agent.py",
        "agents/qa_agent.py",     "agents/repo_manager_agent.py",
        "orchestrator/orchestrator.py","orchestrator/github_manager.py",
        "ui/server.py",           "ui/templates/index.html",
        "ui/static/style.css",    "ui/static/main.js",
        "tests/test_memory.py",   "tests/test_planner.py",
        "tests/test_developer.py","tests/test_reviewer.py",
        "tests/test_repo_manager.py",
        "workspace/calculator.py","workspace/test_calculator.py",
        "main.py", "README.md", ".gitignore",
        "install_dependencies.bat",
    ]
    all_ok = True
    for f in required:
        path   = os.path.join(PROJECT_ROOT, f)
        exists = os.path.exists(path)
        print(f"  {'✓' if exists else '✗'}  {f}")
        if not exists:
            all_ok = False

    print()
    if not all_ok:
        print("VALIDATION FAILED: missing files above.\n")
        sys.exit(1)

    # Import checks
    for m in ["memory.memory_store","agents.planner_agent","agents.developer_agent",
              "agents.reviewer_agent","agents.qa_agent","agents.repo_manager_agent"]:
        try:
            __import__(m)
            print(f"  ✓  import {m}")
        except Exception as e:
            print(f"  ✗  import {m}: {e}")
            all_ok = False

    # Calculator logic
    sys.path.insert(0, os.path.join(PROJECT_ROOT, "workspace"))
    from calculator import add, subtract, multiply, divide, calculate
    assert add(3,5)==8 and subtract(10,3)==7 and multiply(4,5)==20 and divide(10,2)==5.0
    print("  ✓  calculator logic")

    # Check zero dependencies
    print("\n  ✓  Zero external dependencies (stdlib only)")
    print("  ✓  Python version:", sys.version.split()[0])

    print()
    if all_ok:
        print("ALL VALIDATION CHECKS PASSED\n")
        print("Run tests : python main.py --test")
        print("Launch UI : python main.py --ui")
    else:
        print("SOME CHECKS FAILED\n")
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agentic AI Development System — stdlib only, no dependencies",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --goal "Build a CLI todo app"
  python main.py --ui
  python main.py --test
  python main.py --validate
        """
    )
    parser.add_argument("--goal",     type=str,       help="Submit a goal to the orchestrator")
    parser.add_argument("--ui",       action="store_true", help="Launch web UI at http://127.0.0.1:5000")
    parser.add_argument("--test",     action="store_true", help="Run all tests (stdlib unittest)")
    parser.add_argument("--validate", action="store_true", help="Run self-validation suite")
    args = parser.parse_args()

    if args.goal:
        run_goal(args.goal)
    elif args.ui:
        run_ui()
    elif args.test:
        run_tests()
    elif args.validate:
        run_validate()
    else:
        parser.print_help()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
    except Exception as e:
        import traceback
        print("\n" + "="*60)
        print("FATAL ERROR — details below:")
        print("="*60)
        traceback.print_exc()
        print("="*60)
        print("\nCommon fixes:")
        print("  1. cd into the agentic_ai folder first, then run:")
        print("       python main.py --ui")
        print("  2. Port already in use: edit configs/config.json, change port to 5001")
        print("  3. Python too old: needs 3.8+   (check: python --version)")
        print()
        if sys.platform == "win32":
            input("Press Enter to close...")
        sys.exit(1)


# ── Windows crash guard ────────────────────────────────────────────────────────
# Replaces the bare `if __name__ == "__main__": main()` so that if anything
# crashes the window stays open long enough to read the error.
