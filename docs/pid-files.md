# PID File Management

## Overview

Each agent process writes a PID (Process ID) file when it starts, allowing you to monitor running agents and kill them if they hang or crash.

## Location

PID files are stored in the `/pids/` directory:

```
multiagent-loop/
├── pids/
│   ├── planner.pid
│   ├── implementer.pid
│   ├── reviewer.pid
│   ├── tester.pid
│   └── user.pid
```

Each file contains the process ID of the running Claude CLI subprocess.

## Commands

### Check Status

See which agents are currently running:

```bash
uv run agent.py --status
```

Example output:
```
Agent Status:
------------------------------------------------------------
  understand: not running
  planner: RUNNING (PID 650)
  implementer: not running
  reviewer: not running
  tester: not running
  user: not running
```

### Kill a Specific Agent

Stop a hung agent gracefully (SIGTERM):

```bash
uv run agent.py --kill planner
```

Force kill if it won't stop (SIGKILL):

```bash
uv run agent.py --kill planner -9
```

### Kill All Agents

Stop all running agents:

```bash
uv run agent.py --kill-all
```

Force kill all:

```bash
uv run agent.py --kill-all -9
```

## Implementation Details

### Lifecycle

1. **Agent starts**: PID file written before Claude CLI subprocess begins
2. **Agent runs**: PID file exists with valid process ID
3. **Agent completes**: PID file deleted in `finally` block (always runs)

### Stale PID Detection

When checking status, the system validates PIDs are actually running:

```python
def read_pid(role: str) -> int | None:
    pid = int(pid_file.read_text().strip())
    os.kill(pid, 0)  # Signal 0 checks if process exists
    return pid
```

If the process isn't running, the stale PID file is automatically cleaned up.

### Code Location

PID management functions in `agent.py`:

- `write_pid(role, pid)` - Write PID file when agent starts
- `read_pid(role)` - Read and validate PID, clean up if stale
- `clear_pid(role)` - Remove PID file when agent completes
- `kill_agent(role, signal)` - Kill agent by role name
- `kill_all_agents(signal)` - Kill all agents
- `show_status()` - Display status of all agents

## Gitignore

The `/pids/` directory is excluded from version control:

```gitignore
# Agent runtime directories
/workspace/
/agents/
/pids/
```

## Use Cases

### Debugging Hangs

If an agent seems stuck:

```bash
# Check what's running
uv run agent.py --status

# Check the log for the last activity
tail -20 multiagent.log

# Kill the stuck agent
uv run agent.py --kill tester
```

### Cleanup After Crash

If the supervisor crashes mid-run:

```bash
# Kill any orphaned agents
uv run agent.py --kill-all

# Verify cleanup
uv run agent.py --status
```

### Monitoring Long Runs

Watch the log while checking agent status:

```bash
# Terminal 1: Watch log
tail -f multiagent.log

# Terminal 2: Periodic status check
watch -n 5 'uv run agent.py --status'
```
