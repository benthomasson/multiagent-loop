# Multi-Agent Development Loop: Overview

## What This Is

A framework for automated software development using multiple AI agents with distinct roles, coordinated through git and structured around the philosophy that Claude is the user.

## The Three Pillars

### 1. Shared Understanding (Phase 0)

Before development begins, humans and AI build genuine understanding together.

- AI analyzes the task and asks clarifying questions
- Human provides answers and context
- AI validates understanding and checks for contradictions
- Both parties start with the same mental model

**Output:** `SHARED_UNDERSTANDING.md`

See: [Shared Understanding](shared-understanding.md)

### 2. AI-First Design

Software is designed for AI as the primary user:

- Error messages are verbose and structured
- Output is JSON, not pretty tables
- Validation fails fast with all issues enumerated
- Documentation is exhaustive with examples

When AI succeeds immediately, everyone wins.

See: [AI-First Design](ai-first-design.md)

### 3. Claude Is Your User

The User agent actually runs the code and reports friction:

- What worked
- What failed
- What information was missing
- Feature requests: "What would make my job easier?"

The feedback loop collapses from weeks to seconds.

See: [Claude As User](claude-as-user.md)

## The Workflow

```
┌──────────────────────────────────────────────────────────────────┐
│                     PHASE 0: SHARED UNDERSTANDING                 │
│                                                                   │
│   Human describes task → AI asks questions → Human answers →     │
│   AI validates → SHARED_UNDERSTANDING.md                         │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌──────────────────────────────────────────────────────────────────┐
│                     PHASE 1+: DEVELOPMENT LOOP                    │
│                                                                   │
│   ┌─────────┐    ┌─────────────┐    ┌──────────┐                │
│   │ Planner │ →  │ Implementer │ →  │ Reviewer │                │
│   └─────────┘    └─────────────┘    └──────────┘                │
│        ↑                                  │                      │
│        │                                  ▼                      │
│        │         ┌────────┐         ┌────────┐                  │
│        └──────── │  User  │ ←────── │ Tester │                  │
│     (feedback)   └────────┘         └────────┘                  │
│                                                                   │
│   Each stage: self-review + git commit                           │
│   Loop continues until User is SATISFIED                         │
└──────────────────────────────────────────────────────────────────┘
```

## The Agents

| Agent | Role | Output |
|-------|------|--------|
| **Understand** | Build shared understanding with human | SHARED_UNDERSTANDING.md |
| **Planner** | WHAT and WHY, suggests HOW | PLAN.md |
| **Implementer** | Controls HOW, writes code | Code files, IMPLEMENTATION.md |
| **Reviewer** | Feedback to implementer, feed-forward to tester | REVIEW.md |
| **Tester** | Tests and documents usage | Tests, USAGE.md |
| **User** | Actually runs code, requests features | USER_FEEDBACK.md |

## Key Features

### Self-Review at Every Stage

Every agent reflects:
- What went well?
- What information was missing?
- What would make my job easier?

This surfaces friction points throughout the pipeline.

### Git Coordination

Every stage commits to git:
- Checkpoints for recovery
- Audit trail of decisions
- Async review capability
- Full history for debugging

### Iterative Feedback Loop

User feedback drives iterations:
- SATISFIED → Complete
- NEEDS_IMPROVEMENT → Loop back to Planner

The Planner triages feature requests and decides what to implement.

## Usage

```bash
# Phase 0: Build shared understanding
uv run understand.py "build a REST API for user management"

# Phase 1+: Run development loop
uv run supervisor.py --understanding workspace/SHARED_UNDERSTANDING.md "build the API"

# With a directory of context documents
uv run supervisor.py --understanding ./context/ "build the feature"
```

## Human Review Checkpoints

After each iteration, the supervisor:
1. Creates `ITERATION_N_UNDERSTANDING.md` - what agents learned
2. Creates `ITERATION_N_HUMAN_REVIEW.md` - summary for human review
3. Pauses for human to add comments
4. Incorporates comments into next iteration

This keeps humans in the loop while AI does the heavy lifting.

## Why This Approach

### Overcomes Human Limitations
- Short-term memory → External documentation
- System 1 thinking → Structured validation
- Information silos → Cross-platform context gathering

### Overcomes AI Limitations
- Context windows → Persistent documents
- Session isolation → Git-based coordination
- No memory → Full artifact history

### Maximizes the Feedback Loop
- User is always present (it's an AI agent)
- Friction gets articulated immediately
- Improvements compound across iterations

## References

- [Shared Understanding Framework](https://github.com/benthomasson/shared-understanding)
- [FTL2 AI Loop](https://github.com/benthomasson/ftl2-ai-loop)
- [Claude Is Your User (blog)](https://benthomasson.github.io/ai/development/ftl2/2026/02/13/claude-is-your-user.html)
