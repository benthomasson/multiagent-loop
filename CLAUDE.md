# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a multi-agent development loop that orchestrates Claude CLI instances to collaboratively build software. The key insight: Claude is the actual user of the software being built, providing real feedback from real usage.

## Commands

```bash
# Run the full pipeline (from within the target repo)
ftl-sdlc-loop "write a function to check if a number is prime"

# Point to a specific repo
ftl-sdlc-loop --repo /path/to/myproject "add a new feature"

# Feature branches
ftl-sdlc-loop --repo /path/to/repo --branch feature-x "implement feature"
ftl-sdlc-loop --branch feature-x --push  # Push feature branch

# Effort levels
ftl-sdlc-loop --effort minimal "quick fix"     # ~5-15 min, skip review/user
ftl-sdlc-loop --effort moderate "add feature"  # ~30-60 min, balanced
ftl-sdlc-loop --effort maximum "production"    # ~2-3 hours, full pipeline

# Environment variables - load secrets for agents
ftl-sdlc-loop --env ~/.secrets/myproject.env "build API integration"

# Read task from file (for complex prompts)
ftl-sdlc-loop --prompt-file task.md

# Plan review workflow - generate plan, review, then implement
ftl-sdlc-loop --plan-only "build feature X"              # Generate plan only
ftl-sdlc-loop --plan .sdlc-loop/artifacts/PLAN.md "build feature X"  # Use existing plan

# Push changes
ftl-sdlc-loop --push              # Push to remote
ftl-sdlc-loop --pr                # Create a PR

# GitLab workflow - fetch issue, run pipeline, create MR
ftl-sdlc-loop --gitlab-issue 285 --effort minimal
ftl-sdlc-loop --gitlab-mr --push

# GitHub workflow - fix issue, create PR, review
ftl-sdlc-loop --github-issue 29 --github-repo benthomasson/ftl2 --github-pr --code-review --effort moderate --no-questions

# With shared understanding from Phase 0
ftl-sdlc-loop --understanding .sdlc-loop/artifacts/SHARED_UNDERSTANDING.md "build the feature"

# Continue previous agent conversations (for follow-up runs)
ftl-sdlc-loop --continue "fix the bug from last run"

# Continuous mode - process tasks from a queue file
ftl-sdlc-loop --continuous                    # uses queue.txt
ftl-sdlc-loop --continuous --queue tasks.txt  # custom queue file

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

### Three Main Modules

- **understand.py** - Phase 0: Interactive shared understanding builder. Creates `SHARED_UNDERSTANDING.md`.
- **supervisor.py** - Pipeline orchestrator. Runs planner→implementer→reviewer→tester→user loop until satisfied.
- **agent.py** - Low-level agent runner. Handles session isolation, permissions, and PID tracking.

### Working in the Code Repo

Agents work **directly in the target code repository**. All SDLC state (plans, reviews, session dirs, beliefs) lives under `.sdlc-loop/` which is gitignored. This means:

- No separate workspace clone — agents see the real repo
- SDLC artifacts never enter the code repo's git history
- Only actual code changes (from implementer/tester) are committed

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
1. Gets context from `.sdlc-loop/artifacts/` (previous agents' output)
2. Runs with specific tool permissions (`--allowedTools`)
3. Source-modifying agents (implementer, tester) commit code directly

### Key Design Patterns

**Session Isolation**: Each agent runs in `.sdlc-loop/agents/{role}/` directory. Claude CLI stores conversation history per directory, giving each agent persistent memory across iterations.

**Artifact Separation**: SDLC artifacts go to `.sdlc-loop/artifacts/{role}/`. Gitignored — never enters commit history. Only source code changes are committed.

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

### Iteration Entries and Versioned Artifacts

Each agent's output is saved with versioned filenames to preserve the full history:

**Entries** (raw outputs): `.sdlc-loop/entries/iteration-{N}/{role}.md`

**Artifacts** (formatted working files under `.sdlc-loop/artifacts/`):
- `PLAN_{iteration}.md` - Planner output per iteration
- `IMPLEMENTATION_{iteration}_{attempt}.md` - Implementer output per attempt
- `REVIEW_{iteration}_{attempt}.md` - Reviewer output per attempt
- `TESTER_{iteration}_{attempt}.md` - Tester output per attempt
- `USER_FEEDBACK_{iteration}.md` - User feedback per iteration

### Beliefs Integration

The supervisor uses [beliefs](https://github.com/benthomasson/beliefs) as a library (`beliefs_lib`) to track claims across pipeline stages:
- **Planner** decisions → `AXIOM` claims
- **Implementer** files → `DERIVED` claims
- **Reviewer** issues → `WARNING` claims
- **Tester** results → `OBSERVATION` claims

Before the user stage, `beliefs compact` is injected into context. The exit gate also checks: if the user is SATISFIED but active WARNINGs exist, it escalates to a human.

## SDLC State Directory (.sdlc-loop/)

All SDLC state lives under `.sdlc-loop/` in the target repo (gitignored):

```
.sdlc-loop/
├── agents/{role}/          # Claude session dirs (conversation isolation)
├── artifacts/              # SDLC documents (plans, reviews, etc.)
│   ├── TASK.md
│   ├── PLAN_1.md
│   └── {role}/             # Per-agent artifact subdirs
├── entries/iteration-{N}/  # Full agent outputs per iteration
├── beliefs.md              # Beliefs system state
├── nogoods.md              # Contradictions
├── logs/                   # Archived artifacts
├── pids/                   # PID files for running agents
└── multiagent.log          # Verbose logging
```
