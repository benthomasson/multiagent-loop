# Multi-Agent Development Loop

A multi-agent automated software development workflow using Claude CLI.

## Philosophy: Claude Is Your User

The key insight: the **User** agent isn't simulating user stories—it actually runs the code, hits errors, and provides real UX feedback. At the end of each iteration, it asks: **"What would make my job easier?"**

Those feature requests go back to the Planner, who decides which are worth implementing. The loop continues until the User is satisfied.

## Communication Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                           SUPERVISOR                                 │
│                    (orchestrates iterations)                         │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PLANNER (PM + Architect)                                           │
│  • Decides WHAT and WHY                                             │
│  • Suggests HOW (but implementer has final say)                     │
│  • Receives feature requests from User                              │
│  • Decides which requests are worth implementing                    │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  IMPLEMENTER                                                         │
│  • Has ULTIMATE CONTROL of HOW                                       │
│  • Can push back on planner if approach won't work                  │
│  • Writes code with clear error messages                            │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REVIEWER                                                            │
│  • Feedback to implementer (correctness, errors, usability)         │
│  • Feed-forward to tester (what to test, edge cases)                │
│  • Verdict: APPROVED or NEEDS_CHANGES                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TESTER                                                              │
│  • Creates tests based on reviewer notes                            │
│  • Documents HOW TO USE the software                                │
│  • Provides usage instructions to User                              │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  USER (Claude)                                                       │
│  • Actually RUNS the code following tester instructions             │
│  • Reports what worked, what failed, what was confusing             │
│  • Requests features: "What would make my job easier?"              │
│  • Verdict: SATISFIED or NEEDS_IMPROVEMENT                          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ (if NEEDS_IMPROVEMENT)
                                 ▼
                        [loops back to PLANNER]
```

## Usage

### Run the full pipeline

```bash
cd ~/git/multiagent-loop
uv run supervisor.py "write a function to calculate fibonacci numbers"

# With iteration limit
uv run supervisor.py "build a CLI calculator" --max-iterations 5
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
├── supervisor.py      # Pipeline orchestrator with feedback loop
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

2. **Feedback Loop**: User feedback triggers new iterations. The Planner reviews feature requests and decides which to implement.

3. **Convergence**: Loop ends when User is SATISFIED or max iterations reached.

## Key Principles

### Planner vs Implementer

- **Planner** decides WHAT and WHY, suggests HOW
- **Implementer** has ultimate control of HOW, can push back
- This separation prevents the planner from dictating impossible approaches

### Reviewer Feed-Forward

The reviewer doesn't just approve/reject—they provide **feed-forward** to the tester:
- What behaviors need testing
- Edge cases to consider
- Areas of concern

### Tester as Documenter

The tester's job isn't just testing—it's **documenting how to use the software**. The User follows these instructions, making gaps in documentation immediately visible.

### User Feature Requests

The User asks: "What would make my job easier?" These requests go to the Planner, who decides if they're worth implementing. This closes the loop.

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
