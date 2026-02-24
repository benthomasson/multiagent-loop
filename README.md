# Multi-Agent Development Loop

A multi-agent automated software development system using Claude CLI.

## Quick Start (No Install)

```bash
uvx --from git+https://github.com/benthomasson/multiagent-loop multiagent-loop --help
```

## Philosophy: Claude Is Your User

### The Numbers Argument

Every human developer now uses multiple AI agents: code completion, code review, test generation, documentation, refactoring, debugging. A single developer might have 5-10 agents touching their code daily. Multiply that across a team and the ratio becomes clear — **there are already more agents using your code than humans**.

This isn't a future prediction. It's the present. And the gap is only widening. Every new AI-powered dev tool, every IDE integration, every CI/CD agent adds another non-human consumer of your software. The codebase that gets read, executed, and interpreted by 3 humans and 30 agents should be designed for its actual audience.

### What This Means for Software Design

If agents are your primary users, then:

- **Error messages** should be machine-parseable, not just human-readable
- **APIs** should be predictable and self-describing, not clever
- **Documentation** should be structured data, not prose narratives
- **Type hints** aren't optional — they're how agents understand your code
- **Conventions** matter more than creativity — agents rely on patterns

Traditional software development tries to imagine what users want through requirements, user stories, and post-deployment surveys. But when your user is an agent, you can put it directly in the development loop and get immediate, structured, actionable feedback.

### Real Feedback, Not Simulated

The **User** agent in this system isn't simulating user stories — it actually runs the code, hits errors, and provides real UX feedback. This isn't role-playing. Claude is the intended consumer of the software being built.

When the User agent runs `python is_prime.py` and hits an `EOFError`, that's not a test case someone wrote. Claude actually tried to use the software and failed. When it reports "the demo crashed in non-interactive mode," that's genuine feedback from real usage by a real consumer.

| Traditional | Agent-First |
|-------------|------------|
| Hypothetical users | Actual user in the loop |
| Delayed feedback | Real-time feedback |
| Interpreted requirements | Direct requirements |
| "Users might want..." | "I need..." |
| 3 humans read your code | 30 agents read your code |

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

Agents are particularly well-suited as users because:

1. **They articulate frustration** — Unlike humans who abandon software silently, agents explain exactly what went wrong and why
2. **They follow instructions literally** — If documentation is unclear, they fail in instructive ways
3. **They provide structured feedback** — Prioritized feature requests, not vague complaints
4. **They're always available** — No user research scheduling, no interview bias
5. **They represent the majority** — Designing for agents means designing for your actual user base

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

### Quick Start

```bash
# Run from any directory — workspaces are created in cwd
mkdir my-project && cd my-project

# Run a task
multiagent-loop --workspace fibonacci "write a function to calculate fibonacci numbers"

# Fast mode for simple tasks
multiagent-loop --workspace two-sum --effort minimal --no-questions "solve the two-sum problem"
```

### Effort Levels

Control thoroughness vs speed:

```bash
# Fast (~2-5 min): 3 agents, skip review, basic tests
multiagent-loop --effort minimal "solve two-sum"

# Balanced (~30-60 min): 4 agents, code review, decent tests (default)
multiagent-loop --effort moderate "build a REST API"

# Production (~2-3 hours): full 5-agent pipeline, comprehensive testing
multiagent-loop --effort maximum "implement authentication"
```

### Batch Processing

```bash
# Fully automated — no interactive prompts
multiagent-loop --workspace my-task --effort minimal --no-questions "solve the problem"
```

The `--no-questions` flag auto-responds to all agent escalations, ensuring the system never blocks waiting for input. Combined with `--effort minimal`, this enables fully unattended batch processing.

### Named Workspaces

```bash
# Clone a repo into a workspace
multiagent-loop --workspace iris --init-from git@github.com:user/iris.git

# Work on it
multiagent-loop --workspace iris "add a new feature"
multiagent-loop --workspace iris --continue "fix the bug from last run"

# Push changes back (artifacts archived to logs/)
multiagent-loop --workspace iris --push    # Push directly
multiagent-loop --workspace iris --pr      # Or create a PR
```

Workspaces are created in `workspaces/{name}/` relative to where you run the command.

When pushing, artifact files (PLAN.md, REVIEW.md, etc.) are archived to `logs/{workspace}_{timestamp}_artifacts.tar.gz` before being removed from the repo.

### Environment Variables

Load secrets and configuration for agents:

```bash
# Load .env file into workspace and environment
multiagent-loop --workspace myproject --env ~/.secrets/myproject.env "build API integration"

# Can combine with --init-from
multiagent-loop --workspace iris --init-from ~/git/iris --env ~/iris.env "add OAuth support"
```

The `.env` file is:
- Copied to the workspace root
- Automatically added to `.gitignore` (prevents committing secrets)
- Parsed and loaded into the environment for agents to inherit

Supports standard `.env` format: comments (`#`), empty lines, `export` prefix, and quoted values.

### Reading Task from File

For complex task descriptions, read from a file:

```bash
# Create a detailed task file
cat > task.md << 'EOF'
Build a REST API for user management with the following requirements:

- POST /users - Create user (name, email required)
- GET /users/:id - Get user by ID
- PUT /users/:id - Update user
- DELETE /users/:id - Delete user

Use SQLite for storage. Include input validation and proper error responses.
EOF

# Run with the task file
multiagent-loop --workspace user-api --prompt-file task.md
```

### GitLab Integration

Work on GitLab issues directly:

```bash
# Fetch issue #285, assign to self, use description as task
multiagent-loop --workspace issue-285 \
  --gitlab-issue 285 \
  --init-from ~/git/myrepo.git \
  --effort minimal

# After completion, create merge request
multiagent-loop --workspace issue-285 --gitlab-mr --push
```

The `--gitlab-issue` flag:
- Fetches issue title and description via `glab issue view`
- Assigns the issue to your GitLab user
- Uses the issue body as the task prompt (adds `Closes #N`)
- Auto-generates branch name: `fix/issue-285-description-slug`

The `--gitlab-mr` flag:
- Pushes the work branch to origin
- Creates a merge request with the issue title
- Assigns to current user

**Requires:** [glab CLI](https://gitlab.com/gitlab-org/cli) installed and authenticated (`glab auth login`).

### Continuous Mode

Process tasks from a queue file, running unattended:

```bash
echo "write a hello world function" > queue.txt
echo "add error handling" >> queue.txt

multiagent-loop --continuous --effort minimal --no-questions
```

### Shared Understanding

Build context before development:

```bash
multiagent-loop --understanding docs/SHARED_UNDERSTANDING.md "build the feature"
```

### View Results

```bash
cd workspaces/my-task
git log --oneline          # Full audit trail
cat FINAL_REPORT.md        # Summary
cat implementer/*.py       # Generated code
```

## Directory Structure

### Package (installed via uvx)

```
src/multiagent_loop/
├── __init__.py        # Package metadata
├── supervisor.py      # Pipeline orchestrator with feedback loop
├── agent.py           # Agent runner utility
└── understand.py      # Phase 0: Shared understanding builder
```

### Runtime (created in cwd when you run multiagent-loop)

```
your-project/
├── workspaces/        # Named workspaces (each a git repo)
│   └── {workspace}/
│       ├── .git/
│       ├── .env                 # Environment variables (via --env, gitignored)
│       ├── TASK.md, PLAN.md, REVIEW.md, USAGE.md
│       ├── FINAL_REPORT.md
│       ├── implementer/*.py     # Generated code
│       ├── tester/test_*.py     # Generated tests
│       ├── beliefs.md           # Claim tracking
│       └── entries/iteration-{N}/*.md  # Audit trail
├── agents/            # Agent session directories
├── pids/              # PID files for running agents
├── logs/              # Archived artifacts from --push
└── multiagent.log     # Verbose logging
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

## Beliefs Integration

The pipeline integrates [beliefs](https://github.com/benthomasson/beliefs) as a library for tracking claims and contradictions across multi-agent systems.

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

The `beliefs` library is a required dependency — it's declared in supervisor.py's inline script metadata and installed automatically by `uv run`.

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
| `beliefs.md` | Supervisor | Belief registry for claim tracking |
| `ITERATION_N_SUMMARY.md` | Supervisor | Per-iteration summary |
| `FINAL_SUMMARY.md` | Supervisor | Final status and history |

## Installation

```bash
# Install as a CLI tool
uv tool install git+https://github.com/benthomasson/multiagent-loop

# Then use it anywhere
multiagent-loop "write a function to calculate fibonacci numbers"
multiagent-loop --workspace myproject --init-from /path/to/repo
```

Or run directly without installing:

```bash
# Clone and run with uv
git clone https://github.com/benthomasson/multiagent-loop
cd multiagent-loop
uv run supervisor.py "your task here"
```

## Requirements

- [uv](https://github.com/astral-sh/uv) - Python package manager
- [Claude CLI](https://claude.ai/code) - `claude` command available in PATH
- [beliefs](https://github.com/benthomasson/beliefs) - Installed automatically as a dependency
