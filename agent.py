#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Agent runner utility - runs claude -p in a specific agent directory
to maintain separate conversation contexts per agent role.
"""

import subprocess
import os
from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"

def run_agent(role: str, message: str, continue_session: bool = False) -> str:
    """
    Run a claude prompt as a specific agent role.

    Each role has its own directory, so conversations are isolated.
    """
    agent_dir = AGENTS_DIR / role
    if not agent_dir.exists():
        raise ValueError(f"Unknown agent role: {role}")

    cmd = ["claude", "-p", message]
    if continue_session:
        cmd.append("-c")

    # Remove CLAUDECODE env var to allow running from within Claude Code
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=agent_dir
    )

    return result.stdout.strip()

def reset_agent(role: str) -> None:
    """Start a fresh session for an agent by running without -c."""
    run_agent(role, "Starting fresh session.", continue_session=False)

def list_agents() -> list[str]:
    """List available agent roles."""
    return [d.name for d in AGENTS_DIR.iterdir() if d.is_dir()]


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <role> <message>")
        print(f"       {sys.argv[0]} <role> -c <message>  (continue session)")
        print(f"\nAvailable roles: {', '.join(list_agents())}")
        sys.exit(1)

    role = sys.argv[1]
    if sys.argv[2] == "-c":
        message = " ".join(sys.argv[3:])
        continue_session = True
    else:
        message = " ".join(sys.argv[2:])
        continue_session = False

    response = run_agent(role, message, continue_session)
    print(response)
