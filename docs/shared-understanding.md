# Shared Understanding

**Phase 0 of the Multi-Agent Development Loop**

## The Problem

Traditional software development often fails because of misunderstanding, not technical inability. The planner doesn't fully understand the problem. The implementer doesn't understand what the planner meant. The tester doesn't understand what to verify. Each handoff loses context.

AI agents face the same challenge amplified: they start with a task string and must infer everything else. Assumptions go unvalidated. Gaps go unnoticed. The result is wasted iterations.

## The Solution

Before development begins, humans and AI build shared understanding together through structured dialogue.

This isn't just writing a spec—it's collaborative intelligence:

```
Human describes task
       ↓
AI analyzes and identifies gaps
       ↓
AI asks clarifying questions
       ↓
Human provides answers
       ↓
AI validates understanding
       ↓
Both have genuine understanding
```

## How It Works

### Step 1: Initial Analysis

The AI examines the task and produces:

- **What we know** vs **what we don't know**
- **Assumptions** that need validation
- **Information gaps** that could cause problems
- **Clarifying questions** (3-5 specific questions)

### Step 2: Human Input

The human answers the questions. These answers might:

- Confirm assumptions
- Reveal constraints the AI didn't know about
- Clarify priorities
- Provide context from external sources (Jira, Slack, docs)

### Step 3: Validation

The AI validates the updated understanding:

- Checks for contradictions
- Identifies remaining gaps
- Assesses whether understanding is sufficient to proceed
- Highlights potential risks

### Step 4: Shared Understanding Document

The output is `SHARED_UNDERSTANDING.md` containing:

| Section | Purpose |
|---------|---------|
| Problem Statement | Clear statement of what we're solving and why |
| Context | Relevant background information |
| Requirements | What must be true for success |
| Constraints | Limitations we cannot change |
| Assumptions | What we're assuming (with confidence levels) |
| Out of Scope | What we are NOT doing |
| Success Criteria | How we'll know when we're done |
| Open Questions | Things we'll discover during development |
| Key Decisions | Decisions made during understanding phase |

## Why This Matters

### Overcomes Human Limitations

- **Short-term memory** → External documentation captures everything
- **System 1 thinking** → Structured questions force System 2 thinking
- **Familiarity vs understanding** → Validation dialogue catches gaps
- **Information silos** → Can import context from Jira, Slack, docs

### Overcomes AI Limitations

- **Context windows** → Persistent document captures full understanding
- **Temporal confusion** → Explicit structure with clear chronology
- **Session isolation** → Document survives across sessions
- **No memory of past** → Document provides complete history

### Prevents Wasted Work

Without shared understanding:
- Planner makes wrong assumptions → wrong plan
- Implementer misunderstands plan → wrong implementation
- Reviewer doesn't know intent → can't catch logic errors
- User doesn't know expectations → false positives/negatives

With shared understanding:
- All agents reference the same foundation
- Assumptions are validated before work begins
- Gaps are identified before they become bugs
- Everyone knows what "done" means

## Usage

### Interactive Session

```bash
uv run understand.py "build a REST API for user management"
```

The AI will ask clarifying questions. Answer them interactively.

### With External Context

```bash
uv run understand.py "fix the login bug" --context JIRA-123.md slack-thread.txt
```

Import context from files (Jira export, Slack threads, docs).

### Batch Mode

```bash
uv run understand.py "new feature" --answers answers.txt
```

Provide pre-written answers for automated pipelines.

### Using the Output

```bash
uv run supervisor.py --understanding workspace/SHARED_UNDERSTANDING.md "build the feature"
```

The Planner receives the shared understanding document as context.

## Integration with External Tools

The shared understanding phase can import context from:

- **Jira** - Issue details, comments, linked issues
- **Slack** - Relevant thread discussions
- **Google Docs** - Design docs, meeting notes
- **Meeting transcripts** - Recorded discussions

See: [shared-understanding framework](https://github.com/benthomasson/shared-understanding)

## The Key Insight

Shared understanding isn't about documentation—it's about ensuring both human and AI have the same mental model before work begins.

The document is an artifact. The understanding is the goal.
