"""
llm_client.py
Multi-backend LLM client. Switch provider in configs/config.json:

  "llm": { "provider": "anthropic" }   — Anthropic API (urllib, no pip)
  "llm": { "provider": "ollama" }      — Ollama local server (urllib, no pip)
  "llm": { "provider": "huggingface" } — HuggingFace transformers (pip install required)

Falls back to rule-based engine if the selected provider fails or is unavailable.
The rule-based engine requires NO dependencies and always works.
"""

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from typing import Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CONFIG_PATH  = os.path.join(PROJECT_ROOT, "configs", "config.json")

logger = logging.getLogger("LLMClient")

# HuggingFace pipeline is lazy-loaded and cached here after first load
_hf_pipeline = None


# ── Config helper ──────────────────────────────────────────────────────────────

def _cfg() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)

def _provider() -> str:
    return _cfg()["llm"].get("provider", "anthropic").lower()


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND 1 — Anthropic API
# Requires: ANTHROPIC_API_KEY environment variable
# Install:  nothing (uses stdlib urllib)
# ═══════════════════════════════════════════════════════════════════════════════

def _call_anthropic(system: str, prompt: str) -> str:
    cfg     = _cfg()["llm"]["anthropic"]
    api_key = os.environ.get(cfg.get("api_key_env", "ANTHROPIC_API_KEY"), "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    payload = json.dumps({
        "model":       cfg.get("model", "claude-haiku-4-5-20251001"),
        "max_tokens":  cfg.get("max_tokens", 1024),
        "temperature": cfg.get("temperature", 0.3),
        "system":      system,
        "messages":    [{"role": "user", "content": prompt}],
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":          api_key,
            "anthropic-version":  "2023-06-01",
            "content-type":       "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 60)) as resp:
        data = json.loads(resp.read())
    return data["content"][0]["text"].strip()


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND 2 — Ollama (local server)
# Requires: Ollama installed — https://ollama.com
#           Run: ollama pull llama3   (or whichever model you set in config)
# Install:  nothing in Python (uses stdlib urllib)
# ═══════════════════════════════════════════════════════════════════════════════

def _call_ollama(system: str, prompt: str) -> str:
    cfg  = _cfg()["llm"]["ollama"]
    host = cfg.get("host", "http://localhost:11434")
    model = cfg.get("model", "llama3")

    # Build messages in OpenAI-compatible chat format that Ollama accepts
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = json.dumps({
        "model":   model,
        "messages": messages,
        "stream":  False,
        "options": {
            "temperature": cfg.get("temperature", 0.3),
            **cfg.get("options", {}),
        },
    }).encode()

    req = urllib.request.Request(
        f"{host}/api/chat",
        data=payload,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=cfg.get("timeout", 120)) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"].strip()


def _check_ollama_running() -> bool:
    """Return True if Ollama server is reachable."""
    cfg  = _cfg()["llm"]["ollama"]
    host = cfg.get("host", "http://localhost:11434")
    try:
        urllib.request.urlopen(f"{host}/api/tags", timeout=3)
        return True
    except Exception:
        return False


def _list_ollama_models() -> list:
    """Return list of locally available Ollama model names."""
    cfg  = _cfg()["llm"]["ollama"]
    host = cfg.get("host", "http://localhost:11434")
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=5) as resp:
            data = json.loads(resp.read())
        return [m["name"] for m in data.get("models", [])]
    except Exception:
        return []


# ═══════════════════════════════════════════════════════════════════════════════
# BACKEND 3 — HuggingFace Transformers (local, offline)
# Requires: pip install transformers torch accelerate sentencepiece
# Models:   auto-downloaded to models/cache on first use (~1-4 GB)
# ═══════════════════════════════════════════════════════════════════════════════

def _ensure_hf_deps() -> None:
    """Raise ImportError with install instructions if transformers not available."""
    try:
        import transformers  # noqa: F401
        import torch         # noqa: F401
    except ImportError:
        raise ImportError(
            "HuggingFace backend requires extra packages.\n"
            "Run: pip install transformers torch accelerate sentencepiece\n"
            "Or switch provider to 'ollama' or 'anthropic' in configs/config.json"
        )


def _load_hf_pipeline():
    """Lazy-load and cache the HuggingFace pipeline. Returns the pipeline."""
    global _hf_pipeline
    if _hf_pipeline is not None:
        return _hf_pipeline

    _ensure_hf_deps()

    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    import torch

    cfg       = _cfg()["llm"]["huggingface"]
    model_id  = cfg.get("model", "TinyLlama/TinyLlama-1.1B-Chat-v1.0")
    cache_dir = os.path.join(PROJECT_ROOT, cfg.get("cache_dir", "models/cache"))
    device    = cfg.get("device", "cpu")
    load_8bit = cfg.get("load_in_8bit", False)

    os.makedirs(cache_dir, exist_ok=True)
    logger.info(f"[HuggingFace] Loading model: {model_id} (cache: {cache_dir})")

    tokenizer = AutoTokenizer.from_pretrained(
        model_id, cache_dir=cache_dir, trust_remote_code=False
    )

    model_kwargs = dict(
        cache_dir=cache_dir,
        torch_dtype=torch.float16 if device != "cpu" else torch.float32,
        low_cpu_mem_usage=True,
        trust_remote_code=False,
    )
    if load_8bit:
        model_kwargs["load_in_8bit"] = True

    model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)

    _hf_pipeline = pipeline(
        "text-generation",
        model=model,
        tokenizer=tokenizer,
        device=-1 if device == "cpu" else 0,
        framework="pt",
    )
    logger.info(f"[HuggingFace] Model loaded: {model_id}")
    return _hf_pipeline


def _call_huggingface(system: str, prompt: str) -> str:
    cfg        = _cfg()["llm"]["huggingface"]
    max_tokens = cfg.get("max_new_tokens", 512)
    temperature = cfg.get("temperature", 0.3)

    pipe = _load_hf_pipeline()

    # Format as a chat prompt if the model supports it
    full_prompt = f"{system}\n\n{prompt}" if system else prompt

    outputs = pipe(
        full_prompt,
        max_new_tokens=max_tokens,
        temperature=temperature,
        do_sample=True,
        pad_token_id=pipe.tokenizer.eos_token_id,
        truncation=True,
    )
    generated = outputs[0]["generated_text"]
    # Strip the input prompt from the output
    if generated.startswith(full_prompt):
        generated = generated[len(full_prompt):]
    return generated.strip()


def _list_hf_downloaded() -> list:
    """Return list of HuggingFace model dirs found in the cache."""
    cfg       = _cfg()["llm"]["huggingface"]
    cache_dir = os.path.join(PROJECT_ROOT, cfg.get("cache_dir", "models/cache"))
    if not os.path.exists(cache_dir):
        return []
    return [
        d for d in os.listdir(cache_dir)
        if os.path.isdir(os.path.join(cache_dir, d))
    ]


# ═══════════════════════════════════════════════════════════════════════════════
# RULE-BASED FALLBACK
# No dependencies. Always works. Used when all LLM backends fail or are unconfigured.
# ═══════════════════════════════════════════════════════════════════════════════

def _rule_based_planner(goal: str) -> str:
    goal_lower = goal.lower()
    tasks = [
        {"id": "t1", "description": f"Implement: {goal}", "agent": "developer", "depends_on": []},
        {"id": "t2", "description": f"Write pytest tests for: {goal}", "agent": "qa", "depends_on": ["t1"]},
        {"id": "t3", "description": f"Review code for: {goal}", "agent": "reviewer", "depends_on": ["t1"]},
    ]
    if any(w in goal_lower for w in ["calculator", "calc"]):
        tasks = [
            {"id": "t1", "description": "Create calculator.py with add, subtract, multiply, divide functions and CLI main()", "agent": "developer", "depends_on": []},
            {"id": "t2", "description": "Write pytest tests for calculator.py covering all operations and edge cases", "agent": "qa", "depends_on": ["t1"]},
            {"id": "t3", "description": "Review calculator.py for correctness and error handling", "agent": "reviewer", "depends_on": ["t1"]},
        ]
    elif any(w in goal_lower for w in ["todo", "task list", "task manager"]):
        tasks = [
            {"id": "t1", "description": "Create todo.py with add_task, remove_task, list_tasks, complete_task and CLI main()", "agent": "developer", "depends_on": []},
            {"id": "t2", "description": "Write pytest tests for todo.py", "agent": "qa", "depends_on": ["t1"]},
            {"id": "t3", "description": "Review todo.py", "agent": "reviewer", "depends_on": ["t1"]},
        ]
    elif any(w in goal_lower for w in ["password", "passgen", "generator"]):
        tasks = [
            {"id": "t1", "description": "Create password_generator.py with generate_password(length, use_symbols) and CLI main()", "agent": "developer", "depends_on": []},
            {"id": "t2", "description": "Write pytest tests for password_generator.py", "agent": "qa", "depends_on": ["t1"]},
            {"id": "t3", "description": "Review password_generator.py", "agent": "reviewer", "depends_on": ["t1"]},
        ]
    elif any(w in goal_lower for w in ["fibonacci", "fib"]):
        tasks = [
            {"id": "t1", "description": "Create fibonacci.py with fibonacci(n), fibonacci_sequence(n) and CLI main()", "agent": "developer", "depends_on": []},
            {"id": "t2", "description": "Write pytest tests for fibonacci.py", "agent": "qa", "depends_on": ["t1"]},
            {"id": "t3", "description": "Review fibonacci.py", "agent": "reviewer", "depends_on": ["t1"]},
        ]
    return json.dumps({"tasks": tasks})


def _rule_based_developer(goal: str, description: str, filename: str, previous_code: str = "") -> str:
    desc_lower = description.lower()

    if any(w in desc_lower for w in ["calculator", "calc", "add, subtract"]):
        return '''"""CLI calculator: add, subtract, multiply, divide."""
import sys

def add(a, b): return a + b
def subtract(a, b): return a - b
def multiply(a, b): return a * b
def divide(a, b):
    if b == 0: raise ValueError("Division by zero")
    return a / b

OPERATIONS = {"add": add, "+": add, "subtract": subtract, "-": subtract,
              "multiply": multiply, "*": multiply, "divide": divide, "/": divide}

def calculate(op, a, b):
    if op not in OPERATIONS:
        raise ValueError(f"Unknown operation: {op!r}. Use: add, subtract, multiply, divide")
    return OPERATIONS[op](a, b)

def main():
    args = sys.argv[1:]
    if len(args) == 3:
        try: print(calculate(args[0], float(args[1]), float(args[2])))
        except ValueError as e: print(f"Error: {e}", file=sys.stderr); sys.exit(1)
    else:
        print("Calculator — type 'quit' to exit. Usage: op a b")
        while True:
            try: line = input("> ").strip()
            except (EOFError, KeyboardInterrupt): break
            if line.lower() in ("quit", "exit"): break
            parts = line.split()
            if len(parts) != 3: print("Usage: op a b  (e.g. add 3 5)"); continue
            try: print(calculate(parts[0], float(parts[1]), float(parts[2])))
            except ValueError as e: print(f"Error: {e}")

if __name__ == "__main__":
    main()
'''

    if any(w in desc_lower for w in ["todo", "task"]):
        return '''"""CLI todo list manager."""
import sys, json, os

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "todos.json")

def _load():
    if os.path.exists(DB_FILE):
        with open(DB_FILE) as f: return json.load(f)
    return []

def _save(todos):
    with open(DB_FILE, "w") as f: json.dump(todos, f, indent=2)

def add_task(description):
    todos = _load()
    task = {"id": len(todos) + 1, "description": description, "done": False}
    todos.append(task); _save(todos); return task

def remove_task(task_id):
    todos = _load()
    new = [t for t in todos if t["id"] != int(task_id)]
    if len(new) == len(todos): return False
    _save(new); return True

def list_tasks(): return _load()

def complete_task(task_id):
    todos = _load()
    for t in todos:
        if t["id"] == int(task_id): t["done"] = True; _save(todos); return True
    return False

def main():
    args = sys.argv[1:]
    if not args:
        tasks = list_tasks()
        if not tasks: print("No tasks.")
        for t in tasks: print(f"  [{'x' if t['done'] else ' '}] {t['id']}: {t['description']}")
        return
    cmd = args[0]
    if cmd == "add" and len(args) > 1: t = add_task(" ".join(args[1:])); print(f"Added #{t['id']}: {t['description']}")
    elif cmd == "remove" and len(args) > 1: print("Removed." if remove_task(args[1]) else "Not found.")
    elif cmd == "done" and len(args) > 1: print("Done." if complete_task(args[1]) else "Not found.")
    else: print("Usage: todo.py [add <desc>|remove <id>|done <id>]")

if __name__ == "__main__":
    main()
'''

    if any(w in desc_lower for w in ["password", "passgen"]):
        return '''"""CLI password generator."""
import sys, random, string

def generate_password(length=16, use_symbols=True):
    chars = string.ascii_letters + string.digits
    if use_symbols: chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"
    if length < 4: raise ValueError("Password length must be at least 4")
    pwd = [random.choice(string.ascii_lowercase), random.choice(string.ascii_uppercase),
           random.choice(string.digits)]
    if use_symbols: pwd.append(random.choice("!@#$%^&*"))
    pwd += [random.choice(chars) for _ in range(length - len(pwd))]
    random.shuffle(pwd)
    return "".join(pwd)

def main():
    args = sys.argv[1:]
    length = int(args[0]) if args else 16
    symbols = "--no-symbols" not in args
    print(generate_password(length, symbols))

if __name__ == "__main__":
    main()
'''

    if any(w in desc_lower for w in ["fibonacci", "fib"]):
        return '''"""Fibonacci sequence generator."""
import sys

def fibonacci(n):
    if n < 0: raise ValueError("n must be non-negative")
    if n == 0: return 0
    if n == 1: return 1
    a, b = 0, 1
    for _ in range(n - 1): a, b = b, a + b
    return b

def fibonacci_sequence(n):
    return [fibonacci(i) for i in range(n)]

def main():
    args = sys.argv[1:]
    n = int(args[0]) if args else 10
    if "--sequence" in args or len(args) == 0:
        print(fibonacci_sequence(n))
    else:
        print(fibonacci(n))

if __name__ == "__main__":
    main()
'''

    # Generic working stub
    module_name = os.path.splitext(os.path.basename(filename))[0]
    return f'''"""
{module_name}.py — Goal: {goal}
Task: {description}
"""
import sys

def run(args=None):
    """Main logic for {module_name}."""
    if args is None: args = sys.argv[1:]
    print(f"{module_name}: ready. Args: {{args}}")
    return {{"status": "ok", "args": args}}

def main():
    result = run()
    print(result)

if __name__ == "__main__":
    main()
'''


def _rule_based_reviewer(code: str, filename: str) -> str:
    import ast
    issues = []
    try:
        ast.parse(code)
    except SyntaxError as e:
        issues.append(f"SyntaxError line {e.lineno}: {e.msg}")
    if "../" in code or "..\\" in code:
        issues.append("Potential path traversal detected")
    if "os.system(" in code:
        issues.append("Unsafe shell call: os.system()")
    verdict = "reject" if issues else "approve"
    return json.dumps({"verdict": verdict, "issues": issues, "suggestions": "; ".join(issues)})


def _rule_based_qa(module_name: str, code: str) -> str:
    has_main = "def main(" in code
    has_calc = all(f in code for f in ["def add", "def subtract", "def multiply", "def divide"])
    has_todo = all(f in code for f in ["def add_task", "def remove_task", "def list_tasks"])
    has_fib  = "def fibonacci(" in code
    has_pass = "def generate_password(" in code

    if has_calc:
        return f'''"""Tests for {module_name}."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import {module_name}
def test_add():       assert {module_name}.add(3, 5) == 8
def test_subtract():  assert {module_name}.subtract(10, 4) == 6
def test_multiply():  assert {module_name}.multiply(6, 7) == 42
def test_divide():    assert {module_name}.divide(10, 2) == 5.0
def test_div_zero():
    try: {module_name}.divide(1, 0); assert False
    except (ValueError, ZeroDivisionError): pass
def test_calculate(): assert {module_name}.calculate("add", 2, 3) == 5
def test_bad_op():
    try: {module_name}.calculate("modulo", 5, 3); assert False
    except (ValueError, KeyError): pass
'''

    if has_todo:
        return f'''"""Tests for {module_name}."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import {module_name}
def test_add_task():
    t = {module_name}.add_task("test task")
    assert "id" in t and t["description"] == "test task"
def test_list_tasks():
    assert isinstance({module_name}.list_tasks(), list)
def test_remove_task():
    t = {module_name}.add_task("to remove")
    assert {module_name}.remove_task(t["id"]) is True
def test_complete_task():
    t = {module_name}.add_task("to complete")
    assert {module_name}.complete_task(t["id"]) is True
'''

    if has_fib:
        return f'''"""Tests for {module_name}."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import {module_name}
def test_fib_0():  assert {module_name}.fibonacci(0) == 0
def test_fib_1():  assert {module_name}.fibonacci(1) == 1
def test_fib_10(): assert {module_name}.fibonacci(10) == 55
def test_fib_seq():
    seq = {module_name}.fibonacci_sequence(6)
    assert seq == [0, 1, 1, 2, 3, 5]
def test_negative():
    try: {module_name}.fibonacci(-1); assert False
    except ValueError: pass
'''

    if has_pass:
        return f'''"""Tests for {module_name}."""
import sys, os; sys.path.insert(0, os.path.dirname(__file__))
import {module_name}
def test_default_length():  assert len({module_name}.generate_password()) == 16
def test_custom_length():   assert len({module_name}.generate_password(24)) == 24
def test_no_symbols():
    p = {module_name}.generate_password(16, use_symbols=False)
    assert all(c.isalnum() for c in p)
def test_short_raises():
    try: {module_name}.generate_password(2); assert False
    except ValueError: pass
'''

    # Generic smoke test
    return f'''"""Smoke tests for {module_name}."""
import sys, os, importlib; sys.path.insert(0, os.path.dirname(__file__))
def test_import():
    mod = importlib.import_module("{module_name}")
    assert mod is not None
{"def test_main_callable():" if has_main else "def test_placeholder():"}
    {"mod = importlib.import_module('" + module_name + "'); assert callable(mod.main)" if has_main else "    pass"}
'''


# ═══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ═══════════════════════════════════════════════════════════════════════════════

def generate(
    agent_role: str,
    system_prompt: str,
    user_prompt: str,
    goal: str = "",
    description: str = "",
    filename: str = "module.py",
    previous_code: str = "",
    code: str = "",
    module_name: str = "",
) -> str:
    """
    Generate text using the configured provider.
    Priority: configured provider → rule-based fallback.
    Never raises — always returns a usable string.
    """
    provider = _provider()

    # ── Try configured provider ──────────────────────────────────────────────
    if provider == "anthropic":
        try:
            result = _call_anthropic(system_prompt, user_prompt)
            logger.debug(f"[Anthropic] OK ({len(result)} chars)")
            return result
        except Exception as e:
            logger.warning(f"[Anthropic] Failed: {e} — using rule-based fallback")

    elif provider == "ollama":
        try:
            result = _call_ollama(system_prompt, user_prompt)
            logger.debug(f"[Ollama] OK ({len(result)} chars)")
            return result
        except Exception as e:
            logger.warning(f"[Ollama] Failed: {e} — using rule-based fallback")

    elif provider == "huggingface":
        try:
            result = _call_huggingface(system_prompt, user_prompt)
            logger.debug(f"[HuggingFace] OK ({len(result)} chars)")
            return result
        except ImportError as e:
            logger.warning(f"[HuggingFace] Missing deps: {e} — using rule-based fallback")
        except Exception as e:
            logger.warning(f"[HuggingFace] Failed: {e} — using rule-based fallback")

    else:
        logger.warning(f"Unknown provider '{provider}' — using rule-based fallback")

    # ── Rule-based fallback ──────────────────────────────────────────────────
    logger.info(f"[RuleBased] Generating for role={agent_role}")
    if agent_role == "planner":
        return _rule_based_planner(goal)
    elif agent_role == "developer":
        return _rule_based_developer(goal, description, filename, previous_code)
    elif agent_role == "reviewer":
        return _rule_based_reviewer(code, filename)
    elif agent_role == "qa":
        return _rule_based_qa(module_name, code)
    else:
        return f"# Rule-based output for {agent_role}\npass\n"


def get_provider_status() -> dict:
    """
    Return a status dict for all three providers — used by the UI.
    Does lightweight checks without loading models.
    """
    cfg      = _cfg()["llm"]
    provider = cfg.get("provider", "anthropic")

    # Anthropic: check if key is set
    anth_key = os.environ.get(cfg["anthropic"].get("api_key_env", "ANTHROPIC_API_KEY"), "")
    anthropic_ok = bool(anth_key)

    # Ollama: try to reach the server
    ollama_ok     = _check_ollama_running()
    ollama_models = _list_ollama_models() if ollama_ok else []

    # HuggingFace: check if transformers is importable
    try:
        import transformers  # noqa: F401
        hf_available = True
    except ImportError:
        hf_available = False
    hf_downloaded = _list_hf_downloaded() if hf_available else []
    hf_loaded     = _hf_pipeline is not None

    return {
        "active_provider": provider,
        "anthropic": {
            "available": anthropic_ok,
            "model":     cfg["anthropic"].get("model", "?"),
            "key_set":   anthropic_ok,
        },
        "ollama": {
            "available":    ollama_ok,
            "model":        cfg["ollama"].get("model", "?"),
            "host":         cfg["ollama"].get("host", "?"),
            "local_models": ollama_models,
        },
        "huggingface": {
            "available":     hf_available,
            "model":         cfg["huggingface"].get("model", "?"),
            "loaded":        hf_loaded,
            "downloaded":    hf_downloaded,
        },
        "fallback": {
            "available": True,
            "description": "Rule-based engine — always works, no dependencies",
        },
    }
