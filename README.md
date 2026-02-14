# Multi-Agent Development Loop

A multi-agent automated software development workflow using Claude CLI.

## Philosophy: Claude Is Your User

The key insight: the **User** agent isn't simulating user stories—it actually runs the code, hits errors, and provides real UX feedback. This collapses the feedback loop from weeks to seconds.

When AI is the user, you get:
- **Immediate feedback** on confusing error messages
- **Zero-cost usability testing** - if AI struggles, humans will too
- **Precise articulation** of what's broken and what information was missing

## Architecture

```
┌─────────────┐
│  Supervisor │  Orchestrates the pipeline
└──────┬──────┘
       │
       ▼
┌──────────┐    ┌─────────────┐    ┌──────────┐    ┌────────┐    ┌──────┐
│ Planner  │ ─▶ │ Implementer │ ─▶ │ Reviewer │ ─▶ │ Tester │ ─▶ │ User │
└──────────┘    └─────────────┘    └──────────┘    └────────┘    └──────┘
   agents/          agents/           agents/        agents/      agents/
   planner/         implementer/      reviewer/      tester/      user/
```

### Roles

- **Planner** - Analyzes requirements, designs the solution, breaks into tasks
- **Implementer** - Writes the code based on the plan
- **Reviewer** - Reviews for correctness, error handling, and usability
- **Tester** - Creates and runs tests, identifies edge cases
- **User** - Actually uses the code, reports friction points and missing information

## Usage

### Run the full pipeline

```bash
uv run supervisor.py "write a function to calculate fibonacci numbers"
```

### Run individual agents

```bash
uv run agent.py planner "design a REST API for a todo app"
uv run agent.py implementer "implement a binary search function"
uv run agent.py user "try running this code and report issues"

# Continue an agent's conversation
uv run agent.py planner -c "what about error handling?"
```

## Directory Structure

```
multiagent-loop/
├── agent.py           # Agent runner utility
├── supervisor.py      # Pipeline orchestrator
├── agents/            # Agent directories (session isolation)
│   ├── planner/
│   ├── implementer/
│   ├── reviewer/
│   ├── tester/
│   └── user/
└── workspace/         # Output directory for generated code
```

## How It Works

1. **Session Isolation**: Each agent has its own directory. Claude CLI stores conversation history per directory, so each agent maintains its own context.

2. **Pipeline Stages**: The supervisor passes output from each stage to the next. The User stage is critical—it provides real feedback from actually using the code.

3. **Feedback Loop**: User feedback can trigger another iteration (planner revises, implementer fixes, etc.).

## Designing for AI as User

When AI is the primary user, different things matter:

**Error Messages:**
```
# Human-first (bad for AI)
"Connection failed"

# AI-first (good for debugging)
"SSH connection to 'web01' failed: authentication rejected.
 Tried: [publickey]. Expected key at ~/.ssh/id_rsa (exists: true, permissions: 0600).
 Server offered: [publickey, password]."
```

**Output:** Structured JSON with consistent schemas, not pretty tables.

**Validation:** Fail fast with pre-flight checks, enumerate all issues upfront.

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
