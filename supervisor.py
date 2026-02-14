#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Supervisor - orchestrates the multi-agent development loop.

Pipeline stages:
1. Planner - designs the solution, breaks into tasks
2. Implementer - writes the code
3. Reviewer - reviews for issues
4. Tester - creates and runs tests
5. User - actually uses the code, provides UX feedback

The User agent is key: it runs the tools, hits the errors, and reports
what's broken. This collapses the feedback loop from weeks to seconds.

See: "Claude Is Your User" - designing software for AI as the primary user.
"""

import sys
from pathlib import Path
from agent import run_agent

WORKSPACE = Path(__file__).parent / "workspace"

def planner(task: str) -> str:
    """Have the planner design a solution."""
    prompt = f"""You are a software planner/architect. Analyze this task and create a plan:

TASK: {task}

Provide:
1. A brief analysis of the requirements
2. A breakdown of implementation steps
3. Key design decisions
4. What the user should be able to do when it's complete

Be concise and actionable."""

    return run_agent("planner", prompt)

def implementer(plan: str, task: str) -> str:
    """Have the implementer write the code."""
    prompt = f"""You are a software implementer. Write the code based on this plan:

ORIGINAL TASK: {task}

PLAN:
{plan}

Write the implementation. Include clear error messages and structured output
that will help with debugging. Be concise - provide the code."""

    return run_agent("implementer", prompt)

def reviewer(code: str, task: str) -> str:
    """Have the reviewer check the implementation."""
    prompt = f"""You are a code reviewer. Review this implementation:

ORIGINAL TASK: {task}

CODE:
{code}

Check for:
1. Correctness - does it fulfill the task?
2. Error handling - are errors clear and actionable?
3. Usability - can the user (human or AI) easily understand failures?

Verdict: APPROVED or NEEDS_CHANGES
If changes needed, list them."""

    return run_agent("reviewer", prompt)

def tester(code: str, task: str) -> str:
    """Have the tester validate the implementation."""
    prompt = f"""You are a QA tester. Create tests for this implementation:

ORIGINAL TASK: {task}

CODE:
{code}

Provide:
1. Test cases that validate the implementation
2. Edge cases to consider
3. A test script if applicable

Be concise."""

    return run_agent("tester", prompt)

def user(code: str, task: str) -> str:
    """Have the user agent actually use the code and provide feedback."""
    prompt = f"""You are a user of this software. Your job is to actually USE it,
not just review it. Run the code, try different inputs, and report your experience.

ORIGINAL TASK: {task}

CODE:
{code}

Try to accomplish the task using this code. Report:
1. What worked
2. What failed or was confusing
3. What information was missing from error messages
4. What would make this easier to use

Be specific about friction points. If something is unclear, say exactly what
information you needed but didn't have."""

    return run_agent("user", prompt)

def run_pipeline(task: str) -> dict:
    """Run the full development pipeline."""
    results = {}

    print("=" * 60)
    print("SUPERVISOR: Starting development loop")
    print(f"TASK: {task}")
    print("=" * 60)

    # Stage 1: Planning
    print("\n[1/5] PLANNER designing solution...")
    results["planner"] = planner(task)
    print(f"\n{results['planner']}\n")

    # Stage 2: Implementation
    print("\n[2/5] IMPLEMENTER writing code...")
    results["implementer"] = implementer(results["planner"], task)
    print(f"\n{results['implementer']}\n")

    # Stage 3: Review
    print("\n[3/5] REVIEWER checking implementation...")
    results["reviewer"] = reviewer(results["implementer"], task)
    print(f"\n{results['reviewer']}\n")

    # Stage 4: Testing
    print("\n[4/5] TESTER creating tests...")
    results["tester"] = tester(results["implementer"], task)
    print(f"\n{results['tester']}\n")

    # Stage 5: User feedback
    print("\n[5/5] USER trying the code...")
    results["user"] = user(results["implementer"], task)
    print(f"\n{results['user']}\n")

    print("=" * 60)
    print("SUPERVISOR: Pipeline complete")
    print("=" * 60)

    return results


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description>")
        print(f"\nExample: {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    run_pipeline(task)
