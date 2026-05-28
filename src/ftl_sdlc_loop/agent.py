#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Agent runner utility - runs claude -p in a specific agent directory
to maintain separate conversation contexts per agent role.

Each agent has:
- Their own session directory (.sdlc-loop/agents/{role}/) for conversation isolation
- Their own artifact directory (.sdlc-loop/artifacts/{role}/) for SDLC outputs
- Specific tool permissions

Source-modifying agents (implementer, tester) work directly in the code repo root.
All SDLC artifacts are stored under .sdlc-loop/ which is gitignored.
"""

import os
import subprocess
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

# Reasons database path for belief queries
_reasons_db_path: Path | None = None


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


def set_reasons_db(path: Path) -> None:
    """Set the reasons database path for agent prompt injection."""
    global _reasons_db_path
    _reasons_db_path = path


def get_reasons_instructions() -> str:
    """Return prompt section with read-only reasons CLI commands."""
    if _reasons_db_path is None or not _reasons_db_path.exists():
        return ""
    db = _reasons_db_path
    return f"""
## BELIEFS / REASONS SYSTEM

You have access to a belief tracking database via the `reasons` CLI.
Use it to query what is known, what warnings exist, and what decisions were made.

Database path: {db}

Available commands (via Bash):
  reasons --db {db} search "query"        # Search beliefs by keyword
  reasons --db {db} compact --budget 500  # Summarize current belief state
  reasons --db {db} list --status IN      # List all active beliefs
  reasons --db {db} list-gated            # Find beliefs blocked by active problems
  reasons --db {db} explain NODE_ID       # Explain why a belief is IN or OUT
  reasons --db {db} show NODE_ID          # Show full details of a belief
  reasons --db {db} ask "question"        # Ask a question about beliefs

Do NOT use: add, retract, assert, init, or any write commands.
The supervisor manages belief registration.
"""


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


# PID file management
def _pids_dir() -> Path:
    return get_sdlc_dir() / "pids"


def write_pid(role: str, pid: int) -> Path:
    """Write PID file for an agent."""
    pids = _pids_dir()
    pids.mkdir(parents=True, exist_ok=True)
    pid_file = pids / f"{role}.pid"
    pid_file.write_text(str(pid))
    log(f"Wrote PID {pid} to {pid_file}")
    return pid_file


def read_pid(role: str) -> int | None:
    """Read PID for an agent, returns None if not running."""
    pid_file = _pids_dir() / f"{role}.pid"
    if not pid_file.exists():
        return None
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (ValueError, ProcessLookupError, PermissionError):
        pid_file.unlink(missing_ok=True)
        return None


def clear_pid(role: str) -> None:
    """Remove PID file for an agent."""
    pid_file = _pids_dir() / f"{role}.pid"
    if pid_file.exists():
        pid_file.unlink()
        log(f"Cleared PID file for {role}")


def kill_agent(role: str, signal_num: int = 15) -> bool:
    """Kill an agent process by role. Returns True if killed."""
    pid = read_pid(role)
    if pid is None:
        print(f"No running process found for {role}")
        return False
    try:
        os.kill(pid, signal_num)
        print(f"Sent signal {signal_num} to {role} (PID {pid})")
        clear_pid(role)
        return True
    except ProcessLookupError:
        print(f"Process {pid} for {role} not found")
        clear_pid(role)
        return False
    except PermissionError:
        print(f"Permission denied to kill {role} (PID {pid})")
        return False


def kill_all_agents(signal_num: int = 15) -> dict:
    """Kill all running agent processes."""
    results = {}
    for role in AGENT_PERMISSIONS.keys():
        results[role] = kill_agent(role, signal_num)
    return results


def show_status() -> None:
    """Show status of all agents."""
    print("Agent Status:")
    print("-" * 60)
    for role in AGENT_PERMISSIONS.keys():
        pid = read_pid(role)
        if pid:
            print(f"  {role}: RUNNING (PID {pid})")
        else:
            print(f"  {role}: not running")


# Agent permissions configuration
AGENT_PERMISSIONS = {
    "understand": {
        "allowed_tools": ["Read", "Glob", "Grep", "Bash"],
        "can_write": False,
        "description": "Can read files for context gathering, query beliefs",
    },
    "planner": {
        "allowed_tools": ["Read", "Glob", "Grep", "Write", "Bash"],
        "can_write": True,
        "description": "Can read codebase, writes plan, query beliefs",
    },
    "implementer": {
        "allowed_tools": ["Read", "Write", "Edit", "Glob", "Grep", "Bash"],
        "can_write": True,
        "description": "Can read/write/edit files, query beliefs",
    },
    "reviewer": {
        "allowed_tools": ["Read", "Glob", "Grep", "Write", "Bash"],
        "can_write": True,
        "description": "Can read files for review, writes review, query beliefs",
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
        ["git"] + args, cwd=cwd, env=env, capture_output=True, text=True
    )


def log_separator(title: str = "NEW RUN"):
    """Add a visible separator in the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = f"\n{'='*60}\n{title} - {timestamp}\n{'='*60}\n"
    f = _get_log_file()
    f.write(separator)
    f.flush()


def setup_agent_workspace(role: str) -> Path:
    """
    Create agent's artifact directory under .sdlc-loop/.
    Returns the agent's artifact directory.
    """
    artifact_dir = get_artifacts_dir() / role
    artifact_dir.mkdir(parents=True, exist_ok=True)
    log(f"Agent artifact dir: {artifact_dir}")
    return artifact_dir


def commit_agent_work(role: str, message: str) -> bool:
    """Commit any code changes the agent made (artifacts are gitignored)."""
    source_modifying_roles = {"implementer", "tester"}
    if role not in source_modifying_roles:
        return False

    repo = get_repo_root()
    log(f"Staging source changes for {role}")

    git_cmd(["add", "--", ".", ":!.sdlc-loop/"], repo)

    result = git_cmd(["diff", "--cached", "--quiet"], repo)
    if result.returncode == 0:
        log(f"No changes to commit for {role}")
        return False

    log(f"Committing changes for {role}: {message}")
    git_cmd(["commit", "-m", f"[{role}] {message}"], repo)
    return True


def get_workspace_context(role: str) -> str:
    """Read relevant files from .sdlc-loop/artifacts/ to provide context to the agent."""
    artifacts = get_artifacts_dir()
    context_parts = []

    shared_files = ["TASK.md", "PLAN.md", "SHARED_UNDERSTANDING.md", "CUMULATIVE_UNDERSTANDING.md"]
    for filename in shared_files:
        filepath = artifacts / filename
        if filepath.exists():
            content = filepath.read_text()[:3000]
            context_parts.append(f"## {filename}\n\n{content}")

    for f in sorted(artifacts.glob("*.md"))[:10]:
        if f.name in shared_files:
            continue
        content = f.read_text()[:2000]
        context_parts.append(f"## {f.name}\n\n{content}")

    agent_order = ["planner", "implementer", "reviewer", "tester", "user"]
    for agent in agent_order:
        if agent == role:
            break
        agent_dir = artifacts / agent
        if agent_dir.exists():
            for f in sorted(agent_dir.glob("*.md"))[:3]:
                content = f.read_text()[:2000]
                context_parts.append(f"## {agent}/{f.name}\n\n{content}")

    return "\n\n---\n\n".join(context_parts) if context_parts else ""


def run_agent(
    role: str, message: str, continue_session: bool = False, auto_commit: bool = True
) -> str:
    """
    Run a claude prompt as a specific agent role.

    Each role has:
    - Session directory (.sdlc-loop/agents/{role}/) for conversation isolation
    - Artifact directory (.sdlc-loop/artifacts/{role}/) for SDLC outputs
    - Source-modifying agents work in the project root directly
    """
    repo = get_repo_root()
    agents_dir = get_agents_dir()

    log(f"{'='*50}")
    log(f"Starting agent: {role.upper()}")
    log(f"{'='*50}")

    agent_session_dir = agents_dir / role
    agent_session_dir.mkdir(parents=True, exist_ok=True)
    log(f"Session directory: {agent_session_dir}")

    agent_artifact_dir = setup_agent_workspace(role)

    permissions = AGENT_PERMISSIONS.get(
        role,
        {
            "allowed_tools": ["Read"],
            "can_write": False,
            "description": "Default: read only",
        },
    )
    log(f"Permissions: {permissions['allowed_tools']}")

    log(f"Gathering workspace context for {role}")
    workspace_context = get_workspace_context(role)
    if workspace_context:
        log(f"Found {len(workspace_context)} chars of context")
    else:
        log("No prior context found")

    source_modifying_roles = {"implementer", "tester"}
    agent_cwd = repo if role in source_modifying_roles else agent_session_dir

    context_dirs = get_context_dirs()
    ref_dirs_section = ""
    if context_dirs:
        dirs_list = "\n".join(f"- {d} (READ ONLY)" for d in context_dirs)
        ref_dirs_section = f"""
Reference directories available for reading (do NOT modify these):
{dirs_list}
"""

    full_prompt = message
    if workspace_context:
        full_prompt = f"""## WORKSPACE CONTEXT

The following files are available from previous stages:

{workspace_context}

---

## YOUR TASK

{message}
"""

    reasons_section = get_reasons_instructions()

    full_prompt += f"""
You are working directly in the project at: {repo}
Write any SDLC output files (plans, reviews, reports) to: {agent_artifact_dir}
Your working directory is {agent_cwd}.
{ref_dirs_section}{reasons_section}"""

    cmd = ["claude", "-p", full_prompt]

    if continue_session:
        cmd.append("-c")

    if "allowed_tools" in permissions:
        cmd.extend(["--allowedTools", ",".join(permissions["allowed_tools"])])

    cmd.extend(["--add-dir", str(repo)])

    for ctx_dir in context_dirs:
        cmd.extend(["--add-dir", ctx_dir])

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    log(f"Running claude command for {role}")
    log(
        f"Command: claude -p '<prompt>' --allowedTools {','.join(permissions.get('allowed_tools', []))}"
    )
    log(f"Working directory: {agent_cwd}")

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
        cwd=agent_cwd,
    )

    write_pid(role, process.pid)

    try:
        stdout, stderr = process.communicate()
        returncode = process.returncode
    finally:
        clear_pid(role)

    log(f"Claude returned with code {returncode}")
    output = stdout.strip()

    class Result:
        pass

    result = Result()
    result.returncode = returncode
    result.stdout = stdout
    result.stderr = stderr

    if result.stderr:
        log(
            f"Stderr: {result.stderr[:200]}",
            "WARN" if result.returncode == 0 else "ERROR",
        )

    if auto_commit and permissions.get("can_write"):
        committed = commit_agent_work(role, f"Work from {role}")
        if committed:
            output += f"\n\n[Committed code changes from {role}]"

    if result.returncode != 0 and result.stderr:
        log(f"Agent {role} failed", "ERROR")
        return f"Error: {result.stderr}\n\nOutput: {output}"

    log(f"Agent {role} completed successfully")
    log(f"Output length: {len(output)} chars")
    return output


def reset_agent(role: str) -> None:
    """Start a fresh session for an agent."""
    run_agent(
        role, "Starting fresh session.", continue_session=False, auto_commit=False
    )


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
        print(f"  Artifacts: .sdlc-loop/artifacts/{role}/")
        print(f"  {perms.get('description', '')}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <role> <message>")
        print(f"       {sys.argv[0]} <role> -c <message>  (continue session)")
        print(f"       {sys.argv[0]} --permissions  (show agent permissions)")
        print(f"       {sys.argv[0]} --status       (show running agents)")
        print(f"       {sys.argv[0]} --kill <role>  (kill a running agent)")
        print(f"       {sys.argv[0]} --kill-all     (kill all running agents)")
        print(f"\nAvailable roles: {', '.join(list_agents())}")
        sys.exit(1)

    if sys.argv[1] == "--status":
        show_status()
        sys.exit(0)

    if sys.argv[1] == "--kill":
        if len(sys.argv) < 3:
            print("Error: role required for --kill")
            sys.exit(1)
        role = sys.argv[2]
        signal_num = 15
        if len(sys.argv) > 3 and sys.argv[3] == "-9":
            signal_num = 9
        kill_agent(role, signal_num)
        sys.exit(0)

    if sys.argv[1] == "--kill-all":
        signal_num = 15
        if len(sys.argv) > 2 and sys.argv[2] == "-9":
            signal_num = 9
        results = kill_all_agents(signal_num)
        killed = sum(1 for v in results.values() if v)
        print(f"Killed {killed} agent(s)")
        sys.exit(0)

    if sys.argv[1] == "--permissions":
        show_permissions()
        sys.exit(0)

    role = sys.argv[1]
    if len(sys.argv) < 3:
        print("Error: message required")
        sys.exit(1)

    if sys.argv[2] == "-c":
        message = " ".join(sys.argv[3:])
        continue_session = True
    else:
        message = " ".join(sys.argv[2:])
        continue_session = False

    response = run_agent(role, message, continue_session)
    print(response)
