#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Agent runner utility - runs claude -p in a specific agent directory
to maintain separate conversation contexts per agent role.

Each agent has specific permissions:
- planner: Read only (plans, doesn't write code)
- implementer: Read + Write + Edit in workspace
- reviewer: Read only (reviews, doesn't modify)
- tester: Read + Write in workspace (creates tests)
- user: Read + Bash (actually runs the code)
"""

import subprocess
import os
from pathlib import Path

AGENTS_DIR = Path(__file__).parent / "agents"
WORKSPACE = Path(__file__).parent / "workspace"

# Agent permissions configuration
AGENT_PERMISSIONS = {
    "understand": {
        "allowed_tools": ["Read", "Glob", "Grep"],
        "description": "Can read files for context gathering",
    },
    "planner": {
        "allowed_tools": ["Read", "Glob", "Grep"],
        "description": "Can read files to understand codebase, doesn't write",
    },
    "implementer": {
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep"],
        "add_dirs": [WORKSPACE],
        "description": "Can read/write/edit files in workspace",
    },
    "reviewer": {
        "allowed_tools": ["Read", "Glob", "Grep"],
        "description": "Can read files for review, doesn't modify",
    },
    "tester": {
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        "add_dirs": [WORKSPACE],
        "description": "Can create test files and run tests",
    },
    "user": {
        "allowed_tools": ["Read", "Glob", "Grep", "Bash"],
        "add_dirs": [WORKSPACE],
        "description": "Can read code and run it to test",
    },
}


def run_agent(role: str, message: str, continue_session: bool = False,
              extra_context_dirs: list[Path] | None = None) -> str:
    """
    Run a claude prompt as a specific agent role.

    Each role has its own directory (for session isolation) and permissions.
    """
    agent_dir = AGENTS_DIR / role
    agent_dir.mkdir(parents=True, exist_ok=True)

    # Ensure workspace exists
    WORKSPACE.mkdir(parents=True, exist_ok=True)

    # Get agent permissions
    permissions = AGENT_PERMISSIONS.get(role, {
        "allowed_tools": ["Read"],
        "description": "Default: read only",
    })

    # Build command
    cmd = ["claude", "-p", message]

    if continue_session:
        cmd.append("-c")

    # Add allowed tools
    if "allowed_tools" in permissions:
        cmd.extend(["--allowedTools", ",".join(permissions["allowed_tools"])])

    # Add workspace and any extra directories
    dirs_to_add = list(permissions.get("add_dirs", []))
    if extra_context_dirs:
        dirs_to_add.extend(extra_context_dirs)

    for d in dirs_to_add:
        cmd.extend(["--add-dir", str(d)])

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

    if result.returncode != 0 and result.stderr:
        return f"Error: {result.stderr}\n\nOutput: {result.stdout}"

    return result.stdout.strip()


def reset_agent(role: str) -> None:
    """Start a fresh session for an agent by running without -c."""
    run_agent(role, "Starting fresh session.", continue_session=False)


def list_agents() -> list[str]:
    """List available agent roles."""
    return list(AGENT_PERMISSIONS.keys())


def show_permissions():
    """Display permissions for all agents."""
    print("Agent Permissions:")
    print("-" * 60)
    for role, perms in AGENT_PERMISSIONS.items():
        tools = ", ".join(perms.get("allowed_tools", []))
        dirs = ", ".join(str(d) for d in perms.get("add_dirs", []))
        print(f"\n{role}:")
        print(f"  Tools: {tools}")
        if dirs:
            print(f"  Dirs: {dirs}")
        print(f"  {perms.get('description', '')}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <role> <message>")
        print(f"       {sys.argv[0]} <role> -c <message>  (continue session)")
        print(f"       {sys.argv[0]} --permissions  (show agent permissions)")
        print(f"\nAvailable roles: {', '.join(list_agents())}")
        sys.exit(1)

    if sys.argv[1] == "--permissions":
        show_permissions()
        sys.exit(0)

    role = sys.argv[1]
    if len(sys.argv) < 3:
        print(f"Error: message required")
        sys.exit(1)

    if sys.argv[2] == "-c":
        message = " ".join(sys.argv[3:])
        continue_session = True
    else:
        message = " ".join(sys.argv[2:])
        continue_session = False

    response = run_agent(role, message, continue_session)
    print(response)
