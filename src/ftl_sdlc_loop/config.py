"""Shared path configuration and logging for the SDLC loop.

Both agent.py and reasons.py import from here, avoiding circular dependencies.
"""

import sys
from datetime import datetime
from pathlib import Path

# Repo root — the actual code repository agents work in
_repo_root: Path | None = None


def set_repo_root(path: Path) -> None:
    """Set the target code repo root."""
    global _repo_root
    _repo_root = path


def get_repo_root() -> Path:
    """Get the target code repo root. Defaults to CWD."""
    return _repo_root or Path.cwd()


def get_sdlc_dir() -> Path:
    """Get the .sdlc-loop directory for SDLC state."""
    return get_repo_root() / ".sdlc-loop"


def get_artifacts_dir() -> Path:
    """Get the artifacts directory for SDLC documents."""
    return get_sdlc_dir() / "artifacts"


def get_agents_dir() -> Path:
    """Get the agents session directory under .sdlc-loop/."""
    return get_sdlc_dir() / "agents"


# Target branch for commits (default: main)
_target_branch = "main"

# Additional read-only context directories (set via --context-dir)
_context_dirs: list[str] = []


def set_target_branch(branch: str) -> None:
    """Set the target branch for work."""
    global _target_branch
    _target_branch = branch


def get_target_branch() -> str:
    """Get the target branch."""
    return _target_branch


def set_context_dirs(dirs: list[str]) -> None:
    """Set additional read-only context directories for agents."""
    global _context_dirs
    _context_dirs = dirs


def get_context_dirs() -> list[str]:
    """Get additional read-only context directories."""
    return _context_dirs


# Logging
VERBOSE = True
_log_file_handle = None


def _get_log_file():
    """Get or create log file handle."""
    global _log_file_handle
    if _log_file_handle is None:
        log_file = get_sdlc_dir() / "multiagent.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        _log_file_handle = open(log_file, "a")
    return _log_file_handle


def log(msg: str, level: str = "INFO"):
    """Log a message with timestamp to stderr and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {msg}"

    f = _get_log_file()
    f.write(log_line + "\n")
    f.flush()

    if VERBOSE or level in ["ERROR", "WARN"]:
        print(log_line, file=sys.stderr)


def log_separator(title: str = "NEW RUN"):
    """Add a visible separator in the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = f"\n{'='*60}\n{title} - {timestamp}\n{'='*60}\n"
    f = _get_log_file()
    f.write(separator)
    f.flush()
