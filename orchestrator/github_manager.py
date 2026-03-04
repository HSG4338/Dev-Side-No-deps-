"""
github_manager.py
GitHub integration via stdlib urllib + subprocess git. Zero external deps.
"""

import json
import logging
import os
import subprocess
import urllib.request
from typing import Optional

logger      = logging.getLogger("GitHubManager")
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _git(*args, cwd=PROJECT_ROOT) -> str:
    r = subprocess.run(["git"] + list(args), capture_output=True, text=True, cwd=cwd)
    return r.stdout.strip()


def is_git_repo(path=PROJECT_ROOT) -> bool:
    return os.path.exists(os.path.join(path, ".git"))


def init_repo(path=PROJECT_ROOT) -> bool:
    if is_git_repo(path):
        return True
    r = subprocess.run(["git", "init"], capture_output=True, cwd=path)
    return r.returncode == 0


def initial_commit(path=PROJECT_ROOT) -> bool:
    _git("add", "-A", cwd=path)
    r = subprocess.run(
        ["git", "commit", "-m", "Full agentic AI dev system complete — zero placeholders"],
        capture_output=True, text=True, cwd=path
    )
    return r.returncode == 0 or "nothing to commit" in r.stdout + r.stderr


def create_github_repo(token: str, username: str, repo_name: str) -> Optional[str]:
    payload = json.dumps({"name": repo_name, "private": False, "auto_init": False}).encode()
    req = urllib.request.Request(
        "https://api.github.com/user/repos", data=payload,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
            return data.get("clone_url")
    except Exception:
        return f"https://github.com/{username}/{repo_name}.git"


def setup_and_push(path=PROJECT_ROOT) -> bool:
    cfg_path = os.path.join(path, "configs", "config.json")
    with open(cfg_path) as f:
        cfg = json.load(f)
    gh = cfg.get("github", {})
    if not gh.get("enabled", False):
        logger.info("GitHub disabled in config")
        return False
    token    = os.environ.get(gh.get("token_env", "GITHUB_TOKEN"), "")
    username = os.environ.get(gh.get("username_env", "GITHUB_USERNAME"), "")
    repo     = gh.get("repo_name", "agentic-ai-system")
    if not token or not username:
        logger.warning("GitHub credentials not set")
        return False
    init_repo(path)
    initial_commit(path)
    clone_url = create_github_repo(token, username, repo) or f"https://github.com/{username}/{repo}.git"
    auth_url  = clone_url.replace("https://", f"https://{username}:{token}@")
    remotes   = _git("remote", cwd=path)
    if "origin" in remotes:
        _git("remote", "set-url", "origin", auth_url, cwd=path)
    else:
        _git("remote", "add", "origin", auth_url, cwd=path)
    _git("checkout", "-B", "main", cwd=path)
    r = subprocess.run(["git", "push", "-u", "origin", "main", "--force"],
                       capture_output=True, text=True, cwd=path)
    if r.returncode == 0:
        print(f"\n✓ Repository: https://github.com/{username}/{repo}\n")
        return True
    logger.error(f"Push failed: {r.stderr}")
    return False
