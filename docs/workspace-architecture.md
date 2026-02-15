# Workspace Architecture

## Overview

Each agent in the multi-agent loop operates in isolation with:
- **Separate directories** for file operations
- **Specific permissions** limiting what tools they can use
- **Git branches** for version control without conflicts

This design prevents agents from interfering with each other and creates a clear audit trail.

## Directory Structure

```
multiagent-loop/
├── agents/                    # Session directories (conversation isolation)
│   ├── planner/
│   ├── implementer/
│   ├── reviewer/
│   ├── tester/
│   └── user/
│
├── workspace/                 # Shared git repo with agent subdirectories
│   ├── .git/
│   ├── TASK.md               # Shared: task description
│   ├── SHARED_UNDERSTANDING.md
│   ├── CUMULATIVE_UNDERSTANDING.md
│   │
│   ├── planner/              # Planner's workspace
│   │   └── PLAN.md
│   │
│   ├── implementer/          # Implementer's workspace
│   │   ├── is_prime.py
│   │   └── IMPLEMENTATION.md
│   │
│   ├── reviewer/             # Reviewer's workspace
│   │   └── REVIEW.md
│   │
│   ├── tester/               # Tester's workspace
│   │   ├── test_is_prime.py
│   │   └── USAGE.md
│   │
│   └── user/                 # User's workspace
│       └── FEEDBACK.md
│
└── multiagent.log            # Log file for debugging
```

### Two Types of Directories

**Session Directories (`agents/{role}/`)**
- Used for Claude CLI conversation isolation
- Claude stores session history per directory
- Each agent has persistent memory within their session
- Agents can continue conversations with `-c` flag

**Workspace Directories (`workspace/{role}/`)**
- Used for file operations (read, write, edit)
- Each agent writes only to their subdirectory
- All agents can read from all directories
- Version controlled with git

## Agent Permissions

Each agent has specific tools enabled:

| Agent | Read | Write | Edit | Bash | Purpose |
|-------|------|-------|------|------|---------|
| **understand** | ✓ | - | - | - | Gather context, no modifications |
| **planner** | ✓ | ✓ | - | - | Read codebase, write plan |
| **implementer** | ✓ | ✓ | ✓ | - | Full file operations for coding |
| **reviewer** | ✓ | ✓ | - | - | Read code, write review |
| **tester** | ✓ | ✓ | ✓ | ✓ | Create tests, run them |
| **user** | ✓ | ✓ | - | ✓ | Read code, run it, write feedback |

### Permission Rationale

- **Planner** doesn't need Edit (creates new plans, doesn't modify code)
- **Reviewer** doesn't need Edit (reviews, doesn't fix)
- **Implementer** doesn't need Bash (writes code, doesn't run it)
- **Tester** needs Bash to run tests
- **User** needs Bash to actually use the software

### Viewing Permissions

```bash
uv run agent.py --permissions
```

## Git Workflow

### Branches

Each agent works on their own branch:

```
main                    ← Shared state
├── planner            ← Planner's commits
├── implementer        ← Implementer's commits
├── reviewer           ← Reviewer's commits
├── tester             ← Tester's commits
└── user               ← User's commits
```

### Workflow Per Agent

1. **Checkout**: Agent checks out their branch (creates if new)
2. **Merge**: Pull latest changes from `main`
3. **Work**: Agent does their work with permitted tools
4. **Commit**: Changes committed to agent's branch
5. **Merge back**: Supervisor merges agent's branch to `main`

```
┌─────────────────────────────────────────────────────┐
│                    main branch                       │
└─────────────────────────────────────────────────────┘
        │           ↑           ↑           ↑
        ↓           │           │           │
    ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
    │planner│   │implmtr│   │reviewr│   │tester │
    │branch │   │branch │   │branch │   │branch │
    └───────┘   └───────┘   └───────┘   └───────┘
        │           │           │           │
        ↓           ↓           ↓           ↓
    [commits]   [commits]   [commits]   [commits]
```

### Why Branches?

1. **No conflicts**: Each agent writes to their own directory on their own branch
2. **Audit trail**: Git history shows exactly what each agent did
3. **Rollback**: Can revert individual agent's work without affecting others
4. **Parallel work**: Future support for running agents in parallel

### Viewing Branches

```bash
uv run agent.py --branches

# Or directly:
cd workspace && git branch -v
```

### Git Log

```bash
cd workspace && git log --oneline
```

Example output:
```
a1b2c3d [user] Work from user
e4f5g6h [tester] Work from tester
i7j8k9l [reviewer] Work from reviewer
m0n1o2p [implementer] Work from implementer
q3r4s5t [planner] Work from planner
u6v7w8x [supervisor] Start task: write a function...
```

## Context Flow

Each agent receives context from previous stages:

```
Planner receives:
  └── TASK.md, SHARED_UNDERSTANDING.md

Implementer receives:
  ├── TASK.md, SHARED_UNDERSTANDING.md
  └── planner/PLAN.md

Reviewer receives:
  ├── TASK.md, SHARED_UNDERSTANDING.md
  ├── planner/PLAN.md
  └── implementer/*.py, implementer/IMPLEMENTATION.md

Tester receives:
  ├── All of the above
  └── reviewer/REVIEW.md

User receives:
  ├── All of the above
  └── tester/USAGE.md, tester/test_*.py
```

This is automatic - the agent runner gathers context from previous agents' directories and includes it in the prompt.

## Isolation Benefits

### Prevents Interference
- Implementer can't accidentally delete planner's work
- Reviewer can't modify the implementation
- Each agent has clear boundaries

### Clear Ownership
- Every file has a clear owner (the agent whose directory it's in)
- Easy to see who created what
- Blame/attribution is straightforward

### Debugging
- If something goes wrong, check that agent's directory
- Git log shows exactly what changed
- Can diff between iterations

### Recovery
- Roll back one agent's work: `git revert <commit>`
- Reset an agent: delete their branch and directory
- Start fresh: `rm -rf workspace && uv run supervisor.py ...`

## Future: True Forks

The current implementation uses branches on a single repo. A future enhancement could use actual GitHub forks:

```
shared-repo (GitHub)
    ↑
    ├── planner-fork
    ├── implementer-fork
    ├── reviewer-fork
    ├── tester-fork
    └── user-fork
```

Each agent would:
1. Clone their fork
2. Work locally
3. Push to their fork
4. Create PR to shared repo
5. Supervisor merges PRs

This would enable:
- True isolation (separate repos)
- Parallel agents on different machines
- PR-based review before merging
- GitHub Actions for CI on each PR
