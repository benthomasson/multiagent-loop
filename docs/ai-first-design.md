# AI-First Design Philosophy

## The Core Insight

There will be more instances of AI using software than human users.

Every developer spawns multiple AI sessions daily. Most users will interact with software through AI. Background agents multiply horizontally. The ratio of AI instances to human users is rapidly shifting.

Software design should reflect this reality.

## What AI-First Means

AI-first design isn't about replacing humans—it's about recognizing that AI is now a primary consumer of:

- Error messages
- Output formats
- Documentation
- APIs and CLIs
- Configuration systems

When AI can't understand something, it wastes tokens, time, and context debugging. When AI succeeds immediately, everyone wins.

## Design Implications

### Error Messages

**Human-first (bad for AI):**
```
Connection failed
```

**AI-first (good for everyone):**
```
SSH connection to 'web01' failed: authentication rejected.
Tried: [publickey]. Expected key at ~/.ssh/id_rsa (exists: true, permissions: 0600).
Server offered: [publickey, password].
```

The AI can parse structured context and take corrective action. The human reading the AI's summary still gets clarity.

### Output Format

**Human-first:**
```
Pretty tables, colors, progress spinners
```

**AI-first:**
```json
{"status": "success", "hosts": 3, "changed": 2, "failed": 0}
```

Humans can ask AI to summarize structured output. AI cannot reliably parse pretty output.

### Validation

**Human-first:**
- Fail at the point of use
- Let humans figure it out

**AI-first:**
- Fail fast with pre-flight checks
- Enumerate all issues upfront
- Validate before execution

AI debugging is expensive (tokens, time, context). Catching problems before execution saves entire investigation cycles.

### Documentation

**Human-first:**
- Tutorials, guides, conceptual explanations

**AI-first:**
- Exhaustive reference docs
- Examples for every edge case
- Explicit contracts

AI can synthesize understanding from comprehensive reference material. Humans benefit from curated learning paths. Both can coexist.

## AI and Humans Share a Common Language

There's no translation layer between what helps AI and what helps humans:

- Natural language
- Code
- Structured data
- Error messages

When an error message says exactly what went wrong, which file to check, and what the expected value should be—that's better for everyone.

| AI-First Design | Human Benefit |
|-----------------|---------------|
| Verbose, structured errors | No more guessing what went wrong |
| Parseable output formats | Tooling, scripting, automation |
| Pre-flight validation | Faster feedback, less debugging |
| Exhaustive documentation | Answers findable without asking |
| Explicit contracts | Fewer surprises, clearer expectations |

## Native Fluency: Markdown and Python

AI natively "speaks" markdown and Python. No learning curve, no onboarding.

| Format | AI Fluency | Implication |
|--------|------------|-------------|
| Markdown | Native | Documentation, configs, templates work immediately |
| Python | Native | Code examples, scripts, automation work on first try |
| JSON/YAML | Native | Structured data parses cleanly |
| Custom DSLs | Learned | Requires examples, trial and error |
| Proprietary formats | Struggled | May need repeated correction |

**Design implication:** Prefer what AI already knows. A Python-based configuration beats a custom DSL. Markdown documentation beats a proprietary wiki format.

## The Feedback Loop

AI-as-primary-user creates a unique opportunity:

1. AI encounters friction → immediately articulates the problem
2. Problem gets documented with root cause analysis
3. Fix is prioritized by actual time/tokens wasted
4. Improvement benefits all future AI (and human) users

This is faster than traditional user research because the AI can precisely describe what information was missing and what would have helped.

## The User Is Always Present

One of the biggest advantages: the human is right there, at near-zero cost.

**Traditional:**
- User encounters problem → files ticket → waits days → clarifies → waits again

**AI-mediated:**
- AI encounters ambiguity → asks human → gets answer in seconds → continues

The round-trip time for feedback collapses from days to seconds.

## Application to This Project

The multi-agent development loop applies AI-first principles throughout:

### Self-Review at Each Stage

Every agent asks: "What would make my job easier?"

This is AI articulating friction points, exactly as AI-first design prescribes. The feedback goes to the Planner, who decides what to address.

### Structured Artifacts

All outputs are structured markdown:
- `PLAN.md` with clear sections
- `REVIEW.md` with verdict and feed-forward
- `USAGE.md` with step-by-step instructions

Any agent can parse and reference these documents.

### Git Coordination

Every stage commits artifacts. This provides:
- Explicit state that any agent can read
- Full history for debugging
- Async review capability

### The User Agent

The User agent embodies AI-first design: it actually runs the code and reports what's broken. If the User agent struggles:
- Error messages need improvement
- Documentation is unclear
- The interface is too complex

The User agent is automated usability testing.

## References

- [AI-First Design Philosophy](https://github.com/benthomasson/faster-than-light-refactor/entries/2026/02/05/ai-first-design-philosophy.md)
- [Claude Is Your User](https://benthomasson.github.io/ai/development/ftl2/2026/02/13/claude-is-your-user.html)
