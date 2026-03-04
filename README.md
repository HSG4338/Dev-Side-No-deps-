# Agentic AI Development System

**Zero external dependencies. Runs on any Python 3.8+ installation. No pip install required.**

A fully local agentic AI system that plans, writes, reviews, tests, and commits code.
Uses the built-in rule engine by default. Optionally upgrades to full AI via the Anthropic API (set one env var).

---

## Quickstart

```bash
# No install needed — just run:
python main.py --validate
python main.py --goal "Build a CLI calculator with add, subtract, multiply, divide"
python main.py --ui       # → http://127.0.0.1:5000
python main.py --test
```

**Windows**: double-click `install_dependencies.bat` first (runs validation, no downloads).

---

## Optional: AI-Powered Mode

By default the system uses a built-in rule-based engine that works with zero dependencies.

To upgrade to full LLM-powered agents, set one environment variable:

```bash
# Windows
set ANTHROPIC_API_KEY=your_key_here

# Linux / macOS
export ANTHROPIC_API_KEY=your_key_here
```

The system automatically detects the key and switches to the Anthropic API. No other changes needed.

---

## Architecture

```
Goal Input
    │
    ▼
PlannerAgent      → Decomposes goal into task graph
    │
    ▼
DeveloperAgent    → Writes Python files to /workspace
    │
    ▼
ReviewerAgent     → AST static analysis + approval
    │
    ▼
QAAgent           → Generates & runs unittest tests
    │
    ▼
RepoManagerAgent  → Enforces path permissions, snapshots
    │
    ▼
Memory (SQLite)   → All events/decisions persisted
```

---

## Project Structure

```
agentic_ai/
├── agents/
│   ├── base_agent.py
│   ├── planner_agent.py
│   ├── developer_agent.py
│   ├── reviewer_agent.py
│   ├── qa_agent.py
│   └── repo_manager_agent.py
├── orchestrator/
│   ├── orchestrator.py        Main goal loop
│   └── github_manager.py      Git/GitHub integration
├── models/
│   └── llm_client.py          Anthropic API + rule-based fallback
├── memory/
│   └── memory_store.py        SQLite persistence
├── ui/
│   ├── server.py              stdlib http.server (no Flask)
│   ├── templates/index.html   Dark dashboard
│   └── static/                CSS + JS
├── tests/                     stdlib unittest test suite
├── workspace/                 All agent-generated code
├── configs/config.json        System configuration
├── main.py                    CLI entry point
├── install_dependencies.bat   Windows setup script
└── .gitignore
```

---

## Dependencies

| Requirement | Version |
|-------------|---------|
| Python      | 3.8+    |
| pip packages | **None** |
| External services | **None** (unless using API key) |

All stdlib modules used: `sqlite3`, `json`, `http.server`, `threading`, `urllib.request`,
`subprocess`, `ast`, `hashlib`, `shutil`, `unittest`, `argparse`, `logging`, `mimetypes`.

---

## Configuration

Edit `configs/config.json`:

- **llm.model** — Anthropic model to use when API key is set
- **system.max_retries** — retry count per agent
- **github.enabled** — enable git push on completion
- **ui.port** — web UI port (default 5000)

---

## GitHub Integration

```json
// configs/config.json
"github": { "enabled": true, "repo_name": "my-project" }
```

```bash
export GITHUB_TOKEN=your_token
export GITHUB_USERNAME=your_username
```

---

## License

MIT
