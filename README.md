# Multi-Agent Development Loop

A multi-agent automated software development workflow using Claude CLI.

## Philosophy: Claude Is Your User

The key insight: the **User** agent isn't simulating user stories—it actually runs the code, hits errors, and provides real UX feedback. At the end of each stage, every agent asks: **"What would make my job easier?"**

Those feature requests go back to the Planner, who decides which are worth implementing. The loop continues until the User is satisfied.

## Phase 0: Shared Understanding

**Before development begins**, humans and AI build shared understanding together.

This isn't just writing a spec—it's collaborative intelligence:
- AI analyzes the task and identifies gaps
- AI asks clarifying questions
- Human provides answers
- AI validates understanding and checks for contradictions
- Both parties build genuine understanding

```bash
# Interactive shared understanding session
uv run understand.py "build a REST API for user management"

# With context from external sources
uv run understand.py "fix the login bug" --context JIRA-123.md slack-thread.txt
```

This creates `SHARED_UNDERSTANDING.md` which all agents reference.

See: [shared-understanding framework](https://github.com/benthomasson/shared-understanding)

## Key Features

### Git Coordination

Every stage commits to git, providing:
- **Checkpoints** - Recovery points if something goes wrong
- **Audit trail** - Full history of what each agent did and why
- **Visibility** - Human can review commits at any time
- **Async review** - Artifacts persist for later inspection

```
[supervisor] Start task: ...
[planner] Plan for: ...
[implementer] Implement: fibonacci.py
[reviewer] Code review complete
[tester] Tests and usage documentation
[user] User feedback and feature requests
[supervisor] Iteration 1 complete
```

### Self-Review at Each Stage

Every agent reflects after completing their work:
1. What went well?
2. What information was missing?
3. What would make my job easier next time?
4. Confidence level / concerns for next stage

This surfaces friction points and improvement ideas throughout the pipeline, not just at the end.

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
│  • Self-review: What would make planning easier?                    │
│  → [git commit: PLAN.md]                                            │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  IMPLEMENTER                                                         │
│  • Has ULTIMATE CONTROL of HOW                                       │
│  • Can push back on planner if approach won't work                  │
│  • Writes code with clear error messages                            │
│  • Self-review: What was unclear in the plan?                       │
│  → [git commit: implementation files]                               │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  REVIEWER                                                            │
│  • Feedback to implementer (correctness, errors, usability)         │
│  • Feed-forward to tester (what to test, edge cases)                │
│  • Verdict: APPROVED or NEEDS_CHANGES                               │
│  • Self-review: What made review difficult?                         │
│  → [git commit: REVIEW.md]                                          │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TESTER                                                              │
│  • Creates tests based on reviewer notes                            │
│  • Documents HOW TO USE the software                                │
│  • Provides usage instructions to User                              │
│  • Self-review: What gaps did testing reveal?                       │
│  → [git commit: tests + USAGE.md]                                   │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  USER (Claude)                                                       │
│  • Actually RUNS the code following tester instructions             │
│  • Reports what worked, what failed, what was confusing             │
│  • Requests features: "What would make my job easier?"              │
│  • Verdict: SATISFIED or NEEDS_IMPROVEMENT                          │
│  → [git commit: USER_FEEDBACK.md]                                   │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 │ (if NEEDS_IMPROVEMENT)
                                 ▼
                        [loops back to PLANNER]
```

## Usage

### Full Workflow (Recommended)

```bash
cd ~/git/multiagent-loop

# Phase 0: Build shared understanding (interactive)
uv run understand.py "build a REST API for user management"
# Answer the clarifying questions...

# Phase 1+: Run development loop with understanding
uv run supervisor.py --understanding workspace/SHARED_UNDERSTANDING.md "build a REST API for user management"
```

### Quick Start (Skip Phase 0)

```bash
# Run development loop directly (planner works from task alone)
uv run supervisor.py "write a function to calculate fibonacci numbers"

# With iteration limit
uv run supervisor.py "build a CLI calculator" --max-iterations 5
```

### View the git history

After a run, check the workspace:

```bash
cd workspace
git log --oneline
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
├── understand.py      # Phase 0: Shared understanding builder
├── supervisor.py      # Pipeline orchestrator with feedback loop
├── agent.py           # Agent runner utility
├── agents/            # Agent directories (session isolation)
│   ├── understand/    # Phase 0 context
│   ├── planner/
│   ├── implementer/
│   ├── reviewer/
│   ├── tester/
│   └── user/
└── workspace/         # Output directory (git repo with artifacts)
    ├── .git/          # Full commit history
    ├── TASK.md        # Original task
    ├── PLAN.md        # Planner output
    ├── IMPLEMENTATION.md
    ├── REVIEW.md
    ├── USAGE.md
    ├── USER_FEEDBACK.md
    ├── ITERATION_*_SUMMARY.md
    ├── FINAL_SUMMARY.md
    └── *.py           # Generated code files
```

## How It Works

1. **Session Isolation**: Each agent has its own directory. Claude CLI stores conversation history per directory, so each agent maintains its own context.

2. **Git Coordination**: Every stage commits artifacts. This provides checkpoints, audit trail, and async review capability.

3. **Self-Review**: Each agent reflects on their work, surfacing friction points and improvement ideas.

4. **Feedback Loop**: User feedback triggers new iterations. The Planner reviews feature requests and decides which to implement.

5. **Convergence**: Loop ends when User is SATISFIED or max iterations reached.

## Artifacts Generated

| File | Created By | Purpose |
|------|------------|---------|
| `INITIAL_ANALYSIS.md` | Understand | Initial task analysis and questions |
| `VALIDATION.md` | Understand | Human answers and validation |
| `SHARED_UNDERSTANDING.md` | Understand | Final shared understanding document |
| `TASK.md` | Supervisor | Original task description |
| `PLAN.md` | Planner | Requirements, design decisions, success criteria |
| `IMPLEMENTATION.md` | Implementer | Implementation notes and self-review |
| `*.py` | Implementer | Generated code files |
| `REVIEW.md` | Reviewer | Code review with feedback and feed-forward |
| `USAGE.md` | Tester | Usage instructions for the User |
| `test_*.py` | Tester | Test files |
| `USER_FEEDBACK.md` | User | Usage report and feature requests |
| `ITERATION_N_SUMMARY.md` | Supervisor | Per-iteration summary |
| `FINAL_SUMMARY.md` | Supervisor | Final status and history |

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
