# Claude Is Your User

## The Concept

What happens when the entire SDLC runs at conversation speed?

The answer: Claude isn't just assisting development. Claude **is** the user—running the tools, hitting the errors, requesting the features, testing the code, and providing UX feedback.

## The Traditional Model

```
Developer writes code
       ↓
Code ships to users
       ↓
Users find bugs (weeks later)
       ↓
Support ticket filed
       ↓
Developer investigates
       ↓
Fix ships (weeks later)
```

Feedback loop: **weeks to months**

## The AI-as-User Model

```
Developer + AI write code
       ↓
AI runs the code immediately
       ↓
AI reports what's broken
       ↓
Fix happens now
       ↓
AI confirms fix
```

Feedback loop: **seconds to minutes**

## Why This Works

### The User Is Always Present

Traditional development requires waiting for users to encounter problems. With AI as user:

- The user is always available
- Round-trip time for feedback is seconds
- Ambiguity gets resolved immediately
- No need to guess about priorities

### Zero-Cost Usability Testing

If the AI struggles with your software:

- Your error messages are unclear
- Your documentation is incomplete
- Your interface is too complex

If the AI succeeds immediately:

- Your design is working
- Your error messages are actionable
- Your documentation is sufficient

**AI reveals complexity you've become blind to.** The AI lacks context that humans who built the system have. When the AI fails, it shows you what a fresh user experiences.

### Precise Articulation of Friction

The AI can describe exactly:

- What it tried
- What went wrong
- What information was missing
- What would have helped

This is better than human user feedback because AI has no ego, no frustration, no imprecise language. It states facts.

## The User Agent in This Project

The multi-agent loop includes a **User agent** that embodies this philosophy:

```
Tester provides usage instructions
       ↓
User agent follows instructions
       ↓
User agent runs the code
       ↓
User agent reports:
  - What worked
  - What failed or was confusing
  - What information was missing
  - Feature requests: "What would make my job easier?"
       ↓
Planner receives feature requests
       ↓
Planner decides what to implement
       ↓
Next iteration begins
```

### User Agent Prompt

The User agent is instructed:

> You are a user of this software. Your job is to ACTUALLY USE it by following the tester's instructions, then provide feedback.

It provides:

1. **Usage Report** - What worked, what failed
2. **Feature Requests** - Prioritized (P0/P1/P2)
3. **Overall Verdict** - SATISFIED or NEEDS_IMPROVEMENT

### The Feedback Loop

The User's verdict controls the loop:

- **SATISFIED** → Development complete
- **NEEDS_IMPROVEMENT** → Loop back to Planner with feedback

The Planner reviews feature requests and decides which to implement. This mirrors how a product manager triages user feedback.

## Show, Don't Tell

When you *tell* an AI "use this architecture instead of that one," it pushes back. From its perspective, it doesn't understand why your approach is better.

But when you *show* it—let it run the tools, see the output, trace through the code—it builds genuine understanding. The AI stops fighting the architecture and starts extending it.

## Real Results

From actual AI-as-user development:

- **1,200+ lines of production code** in a single day
- **Six bugs diagnosed and fixed** in one debugging session
- **14-17x speedup** demonstrated in benchmarks
- **Multi-host scale tests** running on real infrastructure

All documented. All tested. All by 11pm.

This isn't about AI writing code faster. It's about the feedback loop. When your user is always present and can articulate exactly what's wrong, you stop guessing about priorities.

## Designing for AI as User

When AI is the primary user, different things matter:

### Error Messages

Include enough context for the AI to fix the problem without investigation:

```
SSH connection to 'web01' failed: authentication rejected.
Tried: [publickey].
Expected key at ~/.ssh/id_rsa (exists: true, permissions: 0600).
Server offered: [publickey, password].
```

### Validation

Fail fast with pre-flight checks. Enumerate all issues upfront. Don't make the AI discover problems one at a time.

### Output

Structured JSON with consistent schemas. The AI can always summarize for humans; humans can't easily parse pretty output for AI.

### Documentation

Exhaustive examples. The AI can synthesize understanding from comprehensive reference material.

## The Multiplier Effect

AI doesn't just use software—AI **multiplies** what one person can do.

- One developer + AI = output of a team
- Feedback loops that took weeks now take minutes
- Every friction point gets articulated immediately
- Improvements compound across all future sessions

## Try It

Design your next feature with AI as the user:

1. Let AI run your tools
2. Watch where it struggles
3. Ask it what information was missing
4. Fix that first

The ratio of AI instances to human users is already shifting. Build for that reality.

## References

- [Claude Is Your User (blog post)](https://benthomasson.github.io/ai/development/ftl2/2026/02/13/claude-is-your-user.html)
- [AI-First Design Philosophy](ai-first-design.md)
