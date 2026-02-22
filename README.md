# Multi-Agent Development Loop

A multi-agent automated software development workflow using Claude CLI.

## Philosophy: Claude Is Your User

### The Key Insight

The **User** agent isn't simulating user stories—it actually runs the code, hits errors, and provides real UX feedback. This isn't role-playing. Claude is the intended consumer of the software being built.

Traditional software development tries to imagine what users want:
- Write requirements based on assumptions
- Build features speculatively
- Gather feedback after deployment
- Iterate based on second-hand reports

But here, the user is *in the loop*. We don't have to imagine what Claude wants—we can just ask. When the User agent says "this error message is confusing" or "I wish I could pass a list instead of a single value," that's genuine feedback from the entity that will actually use the code.

### Real Feedback, Not Simulated

When the User agent runs `python is_prime.py` and hits an `EOFError`, that's not a test case someone wrote. Claude actually tried to use the software and failed. When it reports "the demo crashed in non-interactive mode," that's real UX feedback from real usage.

This changes the nature of the feedback loop:

| Traditional | AI-First |
|-------------|----------|
| Hypothetical users | Actual user in the loop |
| Delayed feedback | Real-time feedback |
| Interpreted requirements | Direct requirements |
| "Users might want..." | "I want..." |

### The Self-Review Question

At the end of each stage, every agent asks: **"What would make my job easier?"**

This surfaces friction immediately:
- **Planner**: "The task description was ambiguous about error handling"
- **Implementer**: "The plan didn't specify the expected input format"
- **Reviewer**: "No type hints made the code harder to review"
- **Tester**: "Missing edge case documentation"
- **User**: "The error message didn't tell me what to do next"

Those feature requests go back to the Planner, who decides which are worth implementing. The loop continues until the User is satisfied.

### Why This Works

Claude is particularly well-suited as a user because:

1. **It can articulate frustration** - Unlike real users who abandon software silently, Claude explains exactly what went wrong and why
2. **It follows instructions literally** - If documentation is unclear, Claude will fail in instructive ways
3. **It provides structured feedback** - Prioritized feature requests, not vague complaints
4. **It's always available** - No user research scheduling, no interview bias

The result is software designed for how Claude actually works, with error messages Claude can understand and APIs Claude can use effectively.

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
│  ↑ (if NEEDS_CHANGES: loops back to IMPLEMENTER, up to 3 attempts) │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│  TESTER                                                              │
│  • Creates tests based on reviewer notes                            │
│  • Documents HOW TO USE the software                                │
│  • Provides usage instructions to User                              │
│  • Verdict: TESTS_PASSED or TESTS_FAILED                            │
│  • Self-review: What gaps did testing reveal?                       │
│  → [git commit: tests + USAGE.md]                                   │
│  ↑ (if TESTS_FAILED: loops back to IMPLEMENTER, up to 3 attempts)  │
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

# Continue a previous run (agents remember their prior work)
uv run supervisor.py --continue "fix the bug identified in the last run"

# Combine options
uv run supervisor.py --continue --understanding workspace/ --max-iterations 2 "add input validation"
```

### Continuous Mode

Process tasks from a queue file, running unattended:

```bash
# Create a queue of tasks
echo "write a hello world function" > queue.txt
echo "add error handling" >> queue.txt
echo "write unit tests" >> queue.txt

# Start continuous mode
uv run supervisor.py --continuous

# With options
uv run supervisor.py --continuous --max-iterations 2
uv run supervisor.py --continuous --queue my_tasks.txt
```

Continuous mode:
- Reads the first task from the queue file
- Runs the full pipeline on it
- Removes the completed task from the queue
- When queue is empty, sleeps 60 seconds then checks again
- Add new tasks to the queue file while it's running
- Press Ctrl+C to stop gracefully

### Named Workspaces

Clone existing repos into named workspaces, work on them, and push back:

```bash
# Clone a repo into a workspace (local path or git URL)
uv run supervisor.py --workspace iris --init-from /path/to/iris
uv run supervisor.py --workspace myapp --init-from git@github.com:user/myapp.git

# Work on the codebase
uv run supervisor.py --workspace iris "add a new feature"
uv run supervisor.py --workspace iris --continue "fix the bug from last run"

# Push changes back when done
uv run supervisor.py --workspace iris --push    # Push directly to main
uv run supervisor.py --workspace iris --pr      # Or create a pull request

# Multiple projects can run in parallel
uv run supervisor.py --workspace projectA "implement auth"
uv run supervisor.py --workspace projectB "add logging"
```

Workspaces are cloned into `workspaces/{name}/` with full git history and remote.
Work happens on a `multiagent-work` branch, merged to main on push.
Default workspace is `default` if `--workspace` is not specified.

### View the git history

After a run, check the workspace:

```bash
cd workspaces/iris  # or workspaces/default
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

### Monitor and control agents

```bash
# Check which agents are running
uv run agent.py --status

# Kill a hung agent
uv run agent.py --kill tester

# Force kill (SIGKILL)
uv run agent.py --kill tester -9

# Kill all agents
uv run agent.py --kill-all
```

## Directory Structure

```
multiagent-loop/
├── understand.py      # Phase 0: Shared understanding builder
├── supervisor.py      # Pipeline orchestrator with feedback loop
├── agent.py           # Agent runner utility
├── agents/            # Agent session directories (per workspace)
│   └── {workspace}/   # e.g., "default", "iris", "myproject"
│       ├── planner/
│       ├── implementer/
│       ├── reviewer/
│       ├── tester/
│       └── user/
├── workspaces/        # Named workspaces (each a git repo)
│   └── {workspace}/   # e.g., "default", "iris", "myproject"
│       ├── .git/      # Full commit history
│       ├── TASK.md    # Original task
│       ├── PLAN.md    # Planner output
│       ├── IMPLEMENTATION.md
│       ├── REVIEW.md
│       ├── USAGE.md
│       ├── USER_FEEDBACK.md
│       ├── ITERATION_*_SUMMARY.md
│       ├── FINAL_SUMMARY.md
│       ├── entries/   # Full agent outputs per iteration
│       │   └── iteration-{N}/
│       │       ├── planner.md
│       │       ├── implementer.md
│       │       ├── reviewer.md
│       │       ├── tester.md
│       │       └── user.md
│       ├── beliefs.md # Belief registry (if beliefs CLI installed)
│       ├── nogoods.md # Contradiction database (if beliefs CLI installed)
│       └── *.py       # Generated code files
├── pids/              # PID files for running agents
│   └── {role}.pid     # Contains PID of running agent process
└── multiagent.log     # Verbose logging output
```

## How It Works

1. **Session Isolation**: Each agent has its own directory per workspace (`agents/{workspace}/{role}/`). Claude CLI stores conversation history per directory, so each agent maintains its own context.

2. **Git Coordination**: Every stage commits artifacts. This provides checkpoints, audit trail, and async review capability.

3. **Self-Review**: Each agent reflects on their work, surfacing friction points and improvement ideas.

4. **Inner Loops**: Before reaching the User, two inner feedback loops catch problems early (up to 3 attempts each):
   - **Reviewer → Implementer**: If the reviewer returns `NEEDS_CHANGES`, the implementer fixes issues before testing begins.
   - **Tester → Implementer**: If tests fail (`TESTS_FAILED`), the implementer fixes bugs before the user tries the code.

5. **Outer Feedback Loop**: User feedback triggers new iterations. The Planner reviews feature requests and decides which to implement.

6. **Structured Verdicts & Exit Gates**: Agents emit machine-parseable verdict blocks (`STATUS:` + `OPEN_ISSUES:`) instead of prose. An exit gate catches contradictions — if an agent declares APPROVED but lists open issues, the supervisor overrides the verdict or escalates to a human. This prevents cascading belief failures where bugs propagate through the pipeline because a positive keyword appeared in otherwise-negative feedback.

7. **Convergence**: Loop ends when User is SATISFIED or max iterations reached.

## Beliefs Integration (Optional)

The pipeline optionally integrates with [beliefs](https://github.com/benthomasson/beliefs), a CLI tool for tracking claims and contradictions across multi-agent systems.

### The Problem It Solves

In early test runs, the User agent declared SATISFIED despite documented bugs — the string-matching verdict parser couldn't distinguish "satisfied despite issues" from "satisfied, no issues." Bugs propagated through the pipeline unchallenged because each agent trusted the previous agent's positive verdict without checking the evidence. This is a *cascading belief failure*: one wrong claim ("code is correct") becomes an unquestioned assumption for every downstream agent.

### How It Works

When the `beliefs` CLI is installed, the supervisor registers claims at each pipeline stage:

| After stage | Claim type | Example |
|-------------|------------|---------|
| Planner | `AXIOM` | "Implementation should use recursive approach" |
| Implementer | `DERIVED` | "Created is_prime.py" |
| Reviewer | `WARNING` | "is_prime(4.9) returns True" |
| Tester | `OBSERVATION` | "Tests PASSED" |

Before the User stage, `beliefs compact` produces a structured summary of the current belief state — replacing raw prose accumulation with a queryable snapshot. The exit gate then checks: if the User declares SATISFIED but the beliefs system has active WARNINGs, it escalates to a human rather than terminating the loop.

### Graceful Degradation

All beliefs operations check `beliefs_enabled()` first. If the CLI isn't installed, everything silently no-ops. The pipeline works identically without it — structured verdicts and exit gates function independently.

### Installation

```bash
# Install beliefs CLI (optional)
pip install git+https://github.com/benthomasson/beliefs.git
```

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
| `entries/iteration-N/*.md` | Supervisor | Full agent outputs per iteration (audit trail) |
| `beliefs.md` | Supervisor | Belief registry (optional, requires `beliefs` CLI) |
| `ITERATION_N_SUMMARY.md` | Supervisor | Per-iteration summary |
| `FINAL_SUMMARY.md` | Supervisor | Final status and history |

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
- [beliefs](https://github.com/benthomasson/beliefs) - (Optional) Claim tracking for contradiction detection
