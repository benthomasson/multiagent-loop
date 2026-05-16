# Workspace Architecture

## Overview

Agents work **directly in the target code repository**. All SDLC state — plans, reviews, session history, beliefs — lives under a `.sdlc-loop/` directory that is gitignored. Only actual code changes are committed to the repo.

This design:
- Eliminates agent confusion about which repo they're in
- Keeps SDLC artifacts out of the code repo's git history
- Simplifies the git workflow (no per-agent branches or merge conflicts)

## Directory Structure

```
your-project/                       # The target code repository
├── .sdlc-loop/                     # Gitignored — all SDLC state
│   ├── agents/                     # Session directories (conversation isolation)
│   │   ├── understand/
│   │   ├── planner/
│   │   ├── implementer/
│   │   ├── reviewer/
│   │   ├── tester/
│   │   └── user/
│   │
│   ├── artifacts/                  # SDLC documents
│   │   ├── TASK.md                 # Task description
│   │   ├── SHARED_UNDERSTANDING.md
│   │   ├── CUMULATIVE_UNDERSTANDING.md
│   │   ├── PLAN_1.md              # Versioned artifacts
│   │   ├── IMPLEMENTATION_1_1.md
│   │   ├── REVIEW_1_1.md
│   │   ├── planner/               # Per-agent output dirs
│   │   ├── implementer/
│   │   ├── reviewer/
│   │   ├── tester/
│   │   └── user/
│   │
│   ├── entries/                    # Iteration journals
│   │   └── iteration-1/
│   │       ├── planner.md
│   │       ├── implementer_1.md
│   │       ├── reviewer_1.md
│   │       └── tester_1.md
│   │
│   ├── beliefs.md                  # Beliefs system state
│   ├── nogoods.md                  # Contradictions
│   ├── logs/                       # Archives
│   ├── pids/                       # PID files for running agents
│   └── multiagent.log              # Debug logging
│
├── .gitignore                      # Contains .sdlc-loop/
├── src/                            # Your actual source code
└── tests/                          # Your actual tests
```

### Two Types of Directories

**Session Directories (`.sdlc-loop/agents/{role}/`)**
- Used for Claude CLI conversation isolation
- Claude stores session history per directory
- Each agent has persistent memory within their session
- Agents can continue conversations with `-c` flag

**Artifact Directories (`.sdlc-loop/artifacts/{role}/`)**
- Used for SDLC document output (plans, reviews, reports)
- Each agent writes to their own subdirectory
- All agents can read from all artifact directories
- Gitignored — never enters commit history

## Agent Permissions

Each agent has specific tools enabled:

| Agent | Read | Write | Edit | Bash | Purpose |
|-------|------|-------|------|------|---------|
| **understand** | yes | - | - | - | Gather context, no modifications |
| **planner** | yes | yes | - | - | Read codebase, write plan |
| **implementer** | yes | yes | yes | - | Full file operations for coding |
| **reviewer** | yes | yes | - | - | Read code, write review |
| **tester** | yes | yes | yes | yes | Create tests, run them |
| **user** | yes | yes | - | yes | Read code, run it, write feedback |

### Permission Rationale

- **Planner** doesn't need Edit (creates new plans, doesn't modify code)
- **Reviewer** doesn't need Edit (reviews, doesn't fix)
- **Implementer** doesn't need Bash (writes code, doesn't run it)
- **Tester** needs Bash to run tests
- **User** needs Bash to actually use the software

## Git Workflow

### Direct Commits

Source-modifying agents (implementer, tester) commit directly to the current branch:

```
feature-branch
  ├── [implementer] Implement binary search
  ├── [implementer] Fix review feedback
  ├── [tester] Add test files
  └── (squashed before push)
```

Non-source agents (planner, reviewer, user) produce no commits — their outputs are SDLC artifacts stored in `.sdlc-loop/artifacts/` which is gitignored.

### Push Workflow

When pushing (`--push` or `--pr`), commits are optionally squashed into a single commit for a clean history.

## Context Flow

Each agent receives context from previous agents' artifact directories:

```
Planner receives:
  └── TASK.md, SHARED_UNDERSTANDING.md

Implementer receives:
  ├── TASK.md, SHARED_UNDERSTANDING.md
  └── artifacts/planner/PLAN.md

Reviewer receives:
  ├── TASK.md, SHARED_UNDERSTANDING.md
  ├── artifacts/planner/PLAN.md
  └── artifacts/implementer/*.py, artifacts/implementer/IMPLEMENTATION.md

Tester receives:
  ├── All of the above
  └── artifacts/reviewer/REVIEW.md

User receives:
  ├── All of the above
  └── artifacts/tester/USAGE.md, artifacts/tester/test_*.py
```

This is automatic — the agent runner gathers context from previous agents' artifact directories and includes it in the prompt.

## Isolation Benefits

### Prevents Interference
- SDLC artifacts can't accidentally enter git history
- Agents write to their own artifact directories
- Only code changes are committed

### Clear Ownership
- Every artifact has a clear owner (the agent whose directory it's in)
- Code changes are attributed to the agent that made them
- SDLC state is separate from code state

### Debugging
- Check `.sdlc-loop/artifacts/{role}/` for an agent's output
- Git log shows only meaningful code changes
- `.sdlc-loop/multiagent.log` has verbose debug output

### Simplicity
- No workspace clones to manage
- No per-agent branches or merge conflicts
- Agents work in the real repo — no confusion about context
