#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Agent runner utility - runs claude -p in a specific agent directory
to maintain separate conversation contexts per agent role.

Each agent has:
- Their own session directory (agents/{role}/) for conversation isolation
- Their own workspace subdirectory (workspace/{role}/) for file operations
- Their own git branch for commits
- Specific tool permissions

Workflow:
1. Agent checks out their branch, merges from main
2. Agent reads files from workspace + gets prompt
3. Agent does work (with tools if permitted)
4. Agent commits to their branch
5. Supervisor merges back to main when stage completes
"""

import subprocess
import os
import sys
from pathlib import Path
from datetime import datetime

AGENTS_DIR = Path(__file__).parent / "agents"
WORKSPACE = Path(__file__).parent / "workspace"
LOG_FILE = Path(__file__).parent / "multiagent.log"

# Logging
VERBOSE = True
_log_file_handle = None

def _get_log_file():
    """Get or create log file handle."""
    global _log_file_handle
    if _log_file_handle is None:
        _log_file_handle = open(LOG_FILE, "a")
    return _log_file_handle

def log(msg: str, level: str = "INFO"):
    """Log a message with timestamp to stderr and file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {msg}"

    # Always write to file
    f = _get_log_file()
    f.write(log_line + "\n")
    f.flush()

    # Print to stderr if verbose or error/warn
    if VERBOSE or level in ["ERROR", "WARN"]:
        print(log_line, file=sys.stderr)

# Agent permissions configuration
AGENT_PERMISSIONS = {
    "understand": {
        "allowed_tools": ["Read", "Glob", "Grep"],
        "can_write": False,
        "description": "Can read files for context gathering",
    },
    "planner": {
        "allowed_tools": ["Read", "Glob", "Grep", "Write"],
        "can_write": True,
        "description": "Can read codebase, writes plan to their directory",
    },
    "implementer": {
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep"],
        "can_write": True,
        "description": "Can read/write/edit files in their workspace",
    },
    "reviewer": {
        "allowed_tools": ["Read", "Glob", "Grep", "Write"],
        "can_write": True,
        "description": "Can read files for review, writes review to their directory",
    },
    "tester": {
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        "can_write": True,
        "description": "Can create test files and run tests",
    },
    "user": {
        "allowed_tools": ["Read", "Glob", "Grep", "Bash", "Write"],
        "can_write": True,
        "description": "Can read code, run it, write feedback",
    },
}


def git_cmd(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in the specified directory."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True
    )


def log_separator(title: str = "NEW RUN"):
    """Add a visible separator in the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = f"\n{'='*60}\n{title} - {timestamp}\n{'='*60}\n"
    f = _get_log_file()
    f.write(separator)
    f.flush()


def init_workspace():
    """Initialize the workspace as a git repo if needed."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    git_dir = WORKSPACE / ".git"
    if not git_dir.exists():
        log(f"Initializing workspace git repo at {WORKSPACE}")
        git_cmd(["init"], WORKSPACE)
        (WORKSPACE / ".gitkeep").touch()
        git_cmd(["add", ".gitkeep"], WORKSPACE)
        git_cmd(["commit", "-m", "Initialize workspace"], WORKSPACE)
        log("Workspace initialized")


def setup_agent_branch(role: str) -> Path:
    """
    Set up agent's workspace subdirectory and git branch.
    Returns the agent's workspace directory.
    """
    init_workspace()

    # Create agent's subdirectory
    agent_workspace = WORKSPACE / role
    agent_workspace.mkdir(parents=True, exist_ok=True)
    log(f"Agent workspace: {agent_workspace}")

    # Check if branch exists
    result = git_cmd(["branch", "--list", role], WORKSPACE)
    branch_exists = role in result.stdout

    if not branch_exists:
        log(f"Creating new branch: {role}")
        git_cmd(["checkout", "-b", role], WORKSPACE)
    else:
        log(f"Checking out existing branch: {role}")
        git_cmd(["checkout", role], WORKSPACE)

    # Merge latest from main
    log(f"Merging latest from main into {role}")
    result = git_cmd(["merge", "main", "--no-edit"], WORKSPACE)
    if result.returncode != 0:
        log(f"Merge warning: {result.stderr}", "WARN")

    return agent_workspace


def commit_agent_work(role: str, message: str) -> bool:
    """Commit any changes the agent made."""
    log(f"Checking for changes in {role}/")

    # Stage changes in agent's directory
    git_cmd(["add", role + "/"], WORKSPACE)

    # Check if there are changes to commit
    result = git_cmd(["diff", "--cached", "--quiet"], WORKSPACE)
    if result.returncode == 0:
        log(f"No changes to commit for {role}")
        return False  # No changes

    # Commit
    log(f"Committing changes for {role}: {message}")
    git_cmd(["commit", "-m", f"[{role}] {message}"], WORKSPACE)
    return True


def merge_to_main(role: str) -> bool:
    """Merge agent's branch back to main."""
    log(f"Merging {role} branch back to main")

    # Switch to main
    git_cmd(["checkout", "main"], WORKSPACE)

    # Merge agent's branch
    result = git_cmd(["merge", role, "--no-edit"], WORKSPACE)
    if result.returncode == 0:
        log(f"Successfully merged {role} to main")
    else:
        log(f"Merge failed: {result.stderr}", "ERROR")
    return result.returncode == 0


def get_workspace_context(role: str) -> str:
    """Read relevant files from workspace to provide context to the agent."""
    context_parts = []

    # Read shared files from main workspace
    shared_files = ["TASK.md", "SHARED_UNDERSTANDING.md", "CUMULATIVE_UNDERSTANDING.md"]
    for filename in shared_files:
        filepath = WORKSPACE / filename
        if filepath.exists():
            content = filepath.read_text()[:3000]  # Limit size
            context_parts.append(f"## {filename}\n\n{content}")

    # Read files from other agents' directories (for context)
    agent_order = ["planner", "implementer", "reviewer", "tester", "user"]
    for agent in agent_order:
        if agent == role:
            break  # Only read from previous agents
        agent_dir = WORKSPACE / agent
        if agent_dir.exists():
            for f in sorted(agent_dir.glob("*.md"))[:3]:  # Limit files
                content = f.read_text()[:2000]
                context_parts.append(f"## {agent}/{f.name}\n\n{content}")
            # Also read code files from implementer
            if agent == "implementer":
                for f in sorted(agent_dir.glob("*.py"))[:3]:
                    content = f.read_text()[:3000]
                    context_parts.append(f"## {agent}/{f.name}\n\n```python\n{content}\n```")

    return "\n\n---\n\n".join(context_parts) if context_parts else ""


def run_agent(role: str, message: str, continue_session: bool = False,
              auto_commit: bool = True) -> str:
    """
    Run a claude prompt as a specific agent role.

    Each role has:
    - Session directory (agents/{role}/) for conversation isolation
    - Workspace subdirectory (workspace/{role}/) for file operations
    - Git branch for version control
    """
    log(f"{'='*50}")
    log(f"Starting agent: {role.upper()}")
    log(f"{'='*50}")

    # Set up session directory (for conversation isolation)
    agent_session_dir = AGENTS_DIR / role
    agent_session_dir.mkdir(parents=True, exist_ok=True)
    log(f"Session directory: {agent_session_dir}")

    # Set up workspace and git branch
    agent_workspace = setup_agent_branch(role)

    # Get permissions
    permissions = AGENT_PERMISSIONS.get(role, {
        "allowed_tools": ["Read"],
        "can_write": False,
        "description": "Default: read only",
    })
    log(f"Permissions: {permissions['allowed_tools']}")

    # Get context from workspace
    log(f"Gathering workspace context for {role}")
    workspace_context = get_workspace_context(role)
    if workspace_context:
        log(f"Found {len(workspace_context)} chars of context")
    else:
        log("No prior context found")

    # Build enhanced prompt with context
    full_prompt = message
    if workspace_context:
        full_prompt = f"""## WORKSPACE CONTEXT

The following files are available from previous stages:

{workspace_context}

---

## YOUR TASK

{message}

---

Your workspace directory is: {agent_workspace}
Write any output files to this directory.
"""

    # Build command
    cmd = ["claude", "-p", full_prompt]

    if continue_session:
        cmd.append("-c")

    # Add allowed tools
    if "allowed_tools" in permissions:
        cmd.extend(["--allowedTools", ",".join(permissions["allowed_tools"])])

    # Add workspace directory for file access
    cmd.extend(["--add-dir", str(WORKSPACE)])

    # Remove CLAUDECODE env var to allow running from within Claude Code
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    log(f"Running claude command for {role}")
    log(f"Command: claude -p '<prompt>' --allowedTools {','.join(permissions.get('allowed_tools', []))}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=agent_session_dir
    )

    log(f"Claude returned with code {result.returncode}")
    output = result.stdout.strip()

    if result.stderr:
        log(f"Stderr: {result.stderr[:200]}", "WARN" if result.returncode == 0 else "ERROR")

    # Auto-commit if agent has write permissions
    if auto_commit and permissions.get("can_write"):
        committed = commit_agent_work(role, f"Work from {role}")
        if committed:
            output += f"\n\n[Committed changes to {role} branch]"

    if result.returncode != 0 and result.stderr:
        log(f"Agent {role} failed", "ERROR")
        return f"Error: {result.stderr}\n\nOutput: {output}"

    log(f"Agent {role} completed successfully")
    log(f"Output length: {len(output)} chars")
    return output


def finalize_agent(role: str) -> bool:
    """Merge agent's work back to main branch."""
    return merge_to_main(role)


def reset_agent(role: str) -> None:
    """Start a fresh session for an agent."""
    run_agent(role, "Starting fresh session.", continue_session=False, auto_commit=False)


def list_agents() -> list[str]:
    """List available agent roles."""
    return list(AGENT_PERMISSIONS.keys())


def show_permissions():
    """Display permissions for all agents."""
    print("Agent Permissions:")
    print("-" * 60)
    for role, perms in AGENT_PERMISSIONS.items():
        tools = ", ".join(perms.get("allowed_tools", []))
        can_write = "Yes" if perms.get("can_write") else "No"
        print(f"\n{role}:")
        print(f"  Tools: {tools}")
        print(f"  Can Write: {can_write}")
        print(f"  Workspace: workspace/{role}/")
        print(f"  {perms.get('description', '')}")


def show_branches():
    """Show git branches in workspace."""
    init_workspace()
    result = git_cmd(["branch", "-v"], WORKSPACE)
    print("Workspace branches:")
    print(result.stdout)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <role> <message>")
        print(f"       {sys.argv[0]} <role> -c <message>  (continue session)")
        print(f"       {sys.argv[0]} --permissions  (show agent permissions)")
        print(f"       {sys.argv[0]} --branches     (show workspace branches)")
        print(f"\nAvailable roles: {', '.join(list_agents())}")
        sys.exit(1)

    if sys.argv[1] == "--permissions":
        show_permissions()
        sys.exit(0)

    if sys.argv[1] == "--branches":
        show_branches()
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
