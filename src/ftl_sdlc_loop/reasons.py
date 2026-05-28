"""Wrapper for the `reasons` CLI tool.

The supervisor calls these functions to register and query beliefs.
Agents get read-only CLI access via prompt instructions (see agent.py).
"""

import os
import shutil
import subprocess
from pathlib import Path

from .agent import get_sdlc_dir, log

_reasons_db: Path | None = None


def set_reasons_db(path: Path) -> None:
    global _reasons_db
    _reasons_db = path


def get_reasons_db() -> Path:
    return _reasons_db or get_sdlc_dir() / "reasons.db"


def _find_reasons_bin() -> str:
    found = shutil.which("reasons")
    if found:
        return found
    home = Path.home() / ".local" / "bin" / "reasons"
    if home.exists():
        return str(home)
    return "reasons"


def _run_reasons(*args: str, check: bool = False) -> subprocess.CompletedProcess:
    db = str(get_reasons_db())
    cmd = [_find_reasons_bin(), "--db", db] + list(args)
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
        if result.returncode != 0 and result.stderr:
            log(f"reasons {' '.join(args)}: {result.stderr.strip()}", "WARN")
        if check and result.returncode != 0:
            log(f"reasons command failed: {' '.join(args)}", "ERROR")
        return result
    except FileNotFoundError:
        log("reasons CLI not found — install ftl-reasons", "ERROR")
        return subprocess.CompletedProcess(cmd, 1, "", "reasons: command not found")
    except subprocess.TimeoutExpired:
        log(f"reasons {' '.join(args)}: timed out", "ERROR")
        return subprocess.CompletedProcess(cmd, 1, "", "timeout")


def reasons_init() -> None:
    db = get_reasons_db()
    if db.exists():
        return
    db.parent.mkdir(parents=True, exist_ok=True)
    _run_reasons("init")


def reasons_add(
    node_id: str,
    text: str,
    label: str = "DERIVED",
    depends_on: list[str] | None = None,
    source: str | None = None,
) -> None:
    args = ["add", node_id, text, "--label", label]
    if depends_on:
        args.extend(["--sl", ",".join(depends_on)])
    if source:
        args.extend(["--source", source])
    _run_reasons(*args)


def reasons_compact(budget: int = 500) -> str | None:
    result = _run_reasons("compact", "--budget", str(budget))
    output = result.stdout.strip()
    return output if output else None


def reasons_list_warnings() -> str | None:
    result = _run_reasons("list", "--status", "IN")
    if result.returncode != 0 or not result.stdout.strip():
        return None
    lines = [line for line in result.stdout.strip().split("\n") if "warn" in line.lower()]
    return "\n".join(lines) if lines else None


def reasons_check_stale() -> None:
    result = _run_reasons("check-stale")
    if result.stdout.strip():
        for line in result.stdout.strip().split("\n"):
            print(f"  [reasons] {line}")


def reasons_search(query: str) -> str | None:
    result = _run_reasons("search", query)
    output = result.stdout.strip()
    return output if output else None


def reasons_list_gated() -> str | None:
    result = _run_reasons("list-gated")
    output = result.stdout.strip()
    return output if output else None


def reasons_retract(node_id: str, reason: str | None = None) -> None:
    args = ["retract", node_id]
    if reason:
        args.extend(["--reason", reason])
    _run_reasons(*args)
