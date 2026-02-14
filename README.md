# Multi-Agent Development Loop

A multi-agent automated software development workflow using Claude CLI.

## Architecture

```
┌─────────────┐
│  Supervisor │  Orchestrates the pipeline
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Architect  │ ──▶ │    Coder    │ ──▶ │  Reviewer   │ ──▶ │   Tester    │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
     agents/             agents/             agents/             agents/
     architect/          coder/              reviewer/           tester/
```

Each agent runs in its own directory, giving it an isolated conversation context (Claude CLI stores sessions per directory).

## Usage

### Run the full pipeline

```bash
uv run supervisor.py "write a function to calculate fibonacci numbers"
```

### Run individual agents

```bash
uv run agent.py architect "design a REST API for a todo app"
uv run agent.py coder "implement a binary search function"
uv run agent.py reviewer "review this code: def add(a,b): return a+b"

# Continue an agent's conversation
uv run agent.py architect -c "what about error handling?"
```

## Directory Structure

```
multiagent-loop/
├── agent.py           # Agent runner utility
├── supervisor.py      # Pipeline orchestrator
├── agents/            # Agent directories (session isolation)
│   ├── architect/
│   ├── coder/
│   ├── reviewer/
│   └── tester/
└── workspace/         # Output directory for generated code
```

## How It Works

1. **Session Isolation**: Each agent has its own directory under `agents/`. Claude CLI stores conversation history per directory, so each agent maintains its own context.

2. **Pipeline Stages**: The supervisor passes output from each stage to the next:
   - Architect → designs the solution
   - Coder → implements based on the design
   - Reviewer → checks for issues
   - Tester → creates test cases

3. **Continuation**: Use `-c` flag to continue an agent's conversation for iterative refinement.

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
