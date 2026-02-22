# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a multi-agent development loop that orchestrates Claude CLI instances to collaboratively build software. The key insight: Claude is the actual user of the software being built, providing real feedback from real usage.

## Commands

```bash
# Run the full pipeline
uv run supervisor.py "write a function to check if a number is prime"

# Named workspaces - work on existing codebases
uv run supervisor.py --workspace iris --init-from /path/to/iris  # Clone local repo
uv run supervisor.py --workspace iris --init-from git@github.com:user/repo.git  # Or clone URL
uv run supervisor.py --workspace iris "add a new feature"         # Work on it
uv run supervisor.py --workspace iris --push                      # Push changes back
uv run supervisor.py --workspace iris --pr                        # Or create a PR

# With shared understanding from Phase 0
uv run supervisor.py --understanding workspace/SHARED_UNDERSTANDING.md "build the feature"

# Continue previous agent conversations (for follow-up runs)
uv run supervisor.py --continue "fix the bug from last run"

# Continuous mode - process tasks from a queue file
uv run supervisor.py --continuous                    # uses queue.txt
uv run supervisor.py --continuous --queue tasks.txt  # custom queue file

# Build shared understanding interactively (Phase 0)
uv run understand.py "build a REST API for user management"

# Run individual agents
uv run agent.py planner "design a REST API"
uv run agent.py implementer "implement binary search"
uv run agent.py planner -c "what about error handling?"  # continue conversation

# Monitor agents
uv run agent.py --status        # show running agents
uv run agent.py --kill tester   # kill hung agent
uv run agent.py --kill-all      # kill all agents
uv run agent.py --permissions   # show agent tool permissions
```

## Architecture

### Three Main Scripts

- **understand.py** - Phase 0: Interactive shared understanding builder. Creates `SHARED_UNDERSTANDING.md`.
- **supervisor.py** - Pipeline orchestrator. Runs planner→implementer→reviewer→tester→user loop until satisfied.
- **agent.py** - Low-level agent runner. Handles session isolation, git branches, permissions, and PID tracking.

### Agent Pipeline Flow

```
Planner (WHAT/WHY) → Implementer ←──┬────────────┐
    ↑                    ↓          │            │
    │                 Reviewer ─────┘            │
    │              (if NEEDS_CHANGES)            │
    │                    ↓                       │
    │                 Tester ────────────────────┘
    │              (if TESTS_FAILED)
    │                    ↓
    └───────────────── User
                 (if NEEDS_IMPROVEMENT)
```

**Inner loops** (up to 3 attempts each):
- Reviewer → Implementer: If code needs changes, fix before testing
- Tester → Implementer: If tests fail, fix before user tries it

Each agent:
1. Checks out their git branch, merges from main
2. Gets context from workspace files + previous agents' output
3. Runs with specific tool permissions (`--allowedTools`)
4. Commits to their branch, merges back to main

### Key Design Patterns

**Session Isolation**: Each agent runs in `agents/{workspace}/{role}/` directory. Claude CLI stores conversation history per directory, giving each agent persistent memory across iterations.

**Workspace Separation**: Each agent writes to `workspaces/{workspace}/{role}/`. All can read all directories, but only write to their own.

**Git Coordination**: Every stage commits. Agent branches prevent conflicts. Supervisor merges to main after each stage.

**Conversation Continuation**: Iteration 2+ uses `-c` flag so agents remember previous work. `--continue` flag forces this from iteration 1.

### Agent Permissions (AGENT_PERMISSIONS in agent.py)

| Agent | Tools | Purpose |
|-------|-------|---------|
| understand | Read, Glob, Grep | Context gathering only |
| planner | Read, Glob, Grep, Write | Read codebase, write plan |
| implementer | Read, Write, Edit, Glob, Grep | Full file operations |
| reviewer | Read, Glob, Grep, Write | Read code, write review |
| tester | Read, Write, Edit, Glob, Grep, Bash | Create and run tests |
| user | Read, Glob, Grep, Bash, Write | Run code, write feedback |

### Structured Verdicts

All agents (reviewer, tester, user) emit a structured verdict block at the end of their output:

```
## Verdict
STATUS: APPROVED
OPEN_ISSUES: none
```

or with issues:

```
## Verdict
STATUS: NEEDS_CHANGES
OPEN_ISSUES:
- specific issue 1
- specific issue 2
```

Valid statuses: `APPROVED`/`NEEDS_CHANGES` (reviewer), `TESTS_PASSED`/`TESTS_FAILED` (tester), `SATISFIED`/`NEEDS_IMPROVEMENT` (user).

The supervisor parses `STATUS` and `OPEN_ISSUES` as separate fields. An **exit gate** checks for contradictions: if an agent declares a positive status but lists open issues, the supervisor overrides the verdict (reviewer/tester) or escalates to a human (user).

### Escalation

Agents can request human input with markers like `QUESTION FOR HUMAN:`. Supervisor pauses for input when detected.

### Iteration Entries

Each agent's full output is saved to `entries/iteration-{N}/{role}.md` in the workspace. This provides an immutable audit trail without the truncation of `ITERATION_N_UNDERSTANDING.md`. Inner loop re-runs overwrite the same entry file (captures final state per role per iteration).

### Beliefs Integration (Optional)

If the `beliefs` CLI is installed, the supervisor registers claims after each stage:
- **Planner** decisions → `AXIOM` claims
- **Implementer** files → `DERIVED` claims
- **Reviewer** issues → `WARNING` claims
- **Tester** results → `OBSERVATION` claims

Before the user stage, `beliefs compact` is injected into context. The exit gate also checks: if the user is SATISFIED but active WARNINGs exist, it escalates to a human. All beliefs operations silently no-op if the CLI isn't installed.

## Runtime Directories (gitignored)

- `workspaces/{name}/` - Named workspaces, each a git repo with artifacts and agent subdirectories
  - `entries/iteration-{N}/` - Full agent outputs per iteration (planner.md, implementer.md, etc.)
  - `beliefs.md` / `nogoods.md` - Beliefs system state (if `beliefs` CLI available)
- `agents/{name}/` - Session directories per workspace for conversation isolation
- `pids/` - PID files for running agent processes
- `multiagent.log` - Verbose logging output

Default workspace name is `default` if `--workspace` not specified.
