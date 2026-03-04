"""
memory_store.py
Persistent memory using stdlib sqlite3 only. Zero external dependencies.
Stores goals, tasks, and agent events with full query support.
"""

import json
import os
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_DB   = os.path.join(PROJECT_ROOT, "memory", "memory.db")


def _conn(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str = DEFAULT_DB) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    c = _conn(db_path)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS goals (
            id TEXT PRIMARY KEY, description TEXT NOT NULL,
            status TEXT DEFAULT 'pending', iterations INTEGER DEFAULT 0,
            result TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, goal_id TEXT NOT NULL,
            description TEXT NOT NULL, agent TEXT,
            status TEXT DEFAULT 'pending', result TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
            FOREIGN KEY(goal_id) REFERENCES goals(id)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL, agent TEXT NOT NULL,
            goal_id TEXT, task_id TEXT, data TEXT NOT NULL,
            status TEXT DEFAULT 'info', timestamp REAL NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_ev_goal ON events(goal_id);
        CREATE INDEX IF NOT EXISTS idx_ev_type ON events(event_type);
        CREATE INDEX IF NOT EXISTS idx_task_goal ON tasks(goal_id);
    """)
    c.commit(); c.close()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def log_event(event_type: str, agent: str, data: Dict[str, Any],
              goal_id: str = None, task_id: str = None,
              status: str = "info", db_path: str = DEFAULT_DB) -> int:
    c = _conn(db_path)
    now = time.time()
    cur = c.execute(
        "INSERT INTO events(event_type,agent,goal_id,task_id,data,status,timestamp,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (event_type, agent, goal_id, task_id, json.dumps(data), status, now, datetime.utcfromtimestamp(now).isoformat())
    )
    row_id = cur.lastrowid; c.commit(); c.close()
    return row_id


def create_goal(goal_id: str, description: str, db_path: str = DEFAULT_DB) -> None:
    now = _now_iso()
    c = _conn(db_path)
    c.execute("INSERT OR REPLACE INTO goals(id,description,status,iterations,created_at,updated_at) VALUES(?,?,'pending',0,?,?)",
              (goal_id, description, now, now))
    c.commit(); c.close()


def update_goal(goal_id: str, status: str = None, result: str = None,
                increment_iterations: bool = False, db_path: str = DEFAULT_DB) -> None:
    now = _now_iso()
    c = _conn(db_path)
    if increment_iterations:
        c.execute("UPDATE goals SET iterations=iterations+1, updated_at=? WHERE id=?", (now, goal_id))
    if status:
        c.execute("UPDATE goals SET status=?, updated_at=? WHERE id=?", (status, now, goal_id))
    if result is not None:
        c.execute("UPDATE goals SET result=?, updated_at=? WHERE id=?",
                  (result if isinstance(result, str) else json.dumps(result), now, goal_id))
    c.commit(); c.close()


def create_task(task_id: str, goal_id: str, description: str,
                agent: str = None, db_path: str = DEFAULT_DB) -> None:
    now = _now_iso()
    c = _conn(db_path)
    c.execute("INSERT OR REPLACE INTO tasks(id,goal_id,description,agent,status,created_at,updated_at) VALUES(?,?,?,?,'pending',?,?)",
              (task_id, goal_id, description, agent, now, now))
    c.commit(); c.close()


def update_task(task_id: str, status: str = None, result=None,
                db_path: str = DEFAULT_DB) -> None:
    now = _now_iso()
    c = _conn(db_path)
    if status:
        c.execute("UPDATE tasks SET status=?, updated_at=? WHERE id=?", (status, now, task_id))
    if result is not None:
        c.execute("UPDATE tasks SET result=?, updated_at=? WHERE id=?",
                  (result if isinstance(result, str) else json.dumps(result), now, task_id))
    c.commit(); c.close()


def get_goal(goal_id: str, db_path: str = DEFAULT_DB) -> Optional[Dict]:
    c = _conn(db_path)
    row = c.execute("SELECT * FROM goals WHERE id=?", (goal_id,)).fetchone()
    c.close()
    return dict(row) if row else None


def get_all_goals(db_path: str = DEFAULT_DB) -> List[Dict]:
    c = _conn(db_path)
    rows = c.execute("SELECT * FROM goals ORDER BY created_at DESC").fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_tasks_for_goal(goal_id: str, db_path: str = DEFAULT_DB) -> List[Dict]:
    c = _conn(db_path)
    rows = c.execute("SELECT * FROM tasks WHERE goal_id=? ORDER BY created_at", (goal_id,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def query_events(event_type: str = None, agent: str = None, goal_id: str = None,
                 status: str = None, limit: int = 100, db_path: str = DEFAULT_DB) -> List[Dict]:
    clauses, params = [], []
    if event_type: clauses.append("event_type=?"); params.append(event_type)
    if agent:      clauses.append("agent=?");      params.append(agent)
    if goal_id:    clauses.append("goal_id=?");    params.append(goal_id)
    if status:     clauses.append("status=?");     params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    c = _conn(db_path)
    rows = c.execute(f"SELECT * FROM events {where} ORDER BY timestamp DESC LIMIT ?",
                     params + [limit]).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_recent_events(limit: int = 50, db_path: str = DEFAULT_DB) -> List[Dict]:
    return query_events(limit=limit, db_path=db_path)


# Auto-init on import
init_db()
