#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Supervisor - orchestrates the multi-agent development loop.

Communication Flow:
    Planner (what/why, suggests how)
        ↓
    Implementer (controls how, can push back on planner)
        ↓
    Reviewer (feedback to implementer, feed-forward to tester)
        ↓
    Tester (documents usage, provides instructions to user)
        ↓
    User (actually runs code, requests features from planner)
        ↓
    [loops back to Planner]

The User agent is Claude - it runs the software as it normally would,
then asks: "What would make my job easier?" Those feature requests
go to the Planner who decides if they're worth implementing.

See: "Claude Is Your User" - designing software for AI as the primary user.
"""

import sys
import json
from pathlib import Path
from agent import run_agent

WORKSPACE = Path(__file__).parent / "workspace"

def planner(task: str, user_feedback: str | None = None) -> str:
    """
    Planner: Product Manager + Architect
    Decides WHAT and WHY, suggests HOW.
    Receives feature requests from User and decides if they're worth implementing.
    """
    feedback_section = ""
    if user_feedback:
        feedback_section = f"""
USER FEEDBACK FROM PREVIOUS ITERATION:
{user_feedback}

Consider this feedback. Decide which feature requests are worth implementing.
Explain which you'll address and which you won't (and why).
"""

    prompt = f"""You are a software planner (product manager + architect).
You decide WHAT to build and WHY. You suggest HOW, but the implementer
has final say on implementation approach.

TASK: {task}
{feedback_section}
Provide:
1. Requirements analysis - what exactly needs to be built and why
2. Implementation steps (suggestions for the implementer)
3. Key design decisions
4. Success criteria - what the user should be able to do when complete
5. If addressing user feedback, explain what you're prioritizing and why

Be concise and actionable. The implementer may push back on the HOW."""

    return run_agent("planner", prompt)


def implementer(plan: str, task: str, reviewer_feedback: str | None = None) -> str:
    """
    Implementer: Has ultimate control of HOW.
    Can push back on planner if the suggested approach won't work.
    """
    feedback_section = ""
    if reviewer_feedback:
        feedback_section = f"""
REVIEWER FEEDBACK:
{reviewer_feedback}

Address the reviewer's concerns in your implementation.
"""

    prompt = f"""You are a software implementer. You have ULTIMATE CONTROL of HOW
the software is built. You can push back on the planner's suggestions if
they won't work.

ORIGINAL TASK: {task}

PLANNER'S PLAN:
{plan}
{feedback_section}
Your job:
1. Evaluate the planner's suggested approach
2. If the approach won't work, explain WHY and what you'll do instead
3. Implement the solution with clear error messages and structured output
4. Write code that's easy for users (human or AI) to understand when it fails

Provide the implementation. If you're pushing back on the plan, explain why first."""

    return run_agent("implementer", prompt)


def reviewer(code: str, task: str) -> dict:
    """
    Reviewer: Provides feedback to implementer AND feed-forward to tester.
    Returns structured feedback for both.
    """
    prompt = f"""You are a code reviewer. Review this implementation and provide
feedback for two audiences:

ORIGINAL TASK: {task}

CODE:
{code}

Provide TWO sections:

1. FEEDBACK FOR IMPLEMENTER:
   - Correctness: Does it fulfill the task?
   - Error handling: Are errors clear and actionable?
   - Usability: Can users easily understand failures?
   - Verdict: APPROVED or NEEDS_CHANGES
   - If NEEDS_CHANGES, list specific changes required

2. FEED-FORWARD FOR TESTER:
   - Key behaviors to test
   - Edge cases to consider
   - Suggested test scenarios
   - Any areas of concern to focus testing on

Format your response with clear section headers."""

    response = run_agent("reviewer", prompt)
    return {
        "full_review": response,
        "approved": "APPROVED" in response and "NEEDS_CHANGES" not in response
    }


def tester(code: str, task: str, reviewer_notes: str) -> str:
    """
    Tester: Documents how to use the software.
    Provides usage instructions to the User agent.
    """
    prompt = f"""You are a QA tester. Your job is to:
1. Create tests for this implementation
2. Document HOW TO USE the software for the User

ORIGINAL TASK: {task}

CODE:
{code}

REVIEWER'S NOTES FOR TESTING:
{reviewer_notes}

Provide:

1. TEST CASES:
   - Tests that validate the implementation
   - Edge cases based on reviewer notes
   - A test script if applicable

2. USAGE INSTRUCTIONS FOR USER:
   - Clear step-by-step instructions on how to use this software
   - Example commands or function calls
   - Expected outputs
   - Common error scenarios and what they mean

The User will follow your instructions to actually run the software.
Make the instructions clear enough for someone (human or AI) to follow."""

    return run_agent("tester", prompt)


def user(code: str, task: str, usage_instructions: str) -> dict:
    """
    User: Actually runs the code following tester's instructions.
    Provides feature requests back to Planner.
    """
    prompt = f"""You are a user of this software. Your job is to ACTUALLY USE it
by following the tester's instructions, then provide feedback.

ORIGINAL TASK: {task}

CODE:
{code}

USAGE INSTRUCTIONS FROM TESTER:
{usage_instructions}

Follow the instructions and try to accomplish the task.

After using the software, provide:

1. USAGE REPORT:
   - What worked
   - What failed or was confusing
   - What information was missing from error messages

2. FEATURE REQUESTS:
   What changes would make your job easier? Be specific and practical.
   Think about:
   - What frustrated you?
   - What information were you missing?
   - What capabilities did you wish you had?

3. OVERALL VERDICT:
   - SATISFIED: The software works well enough
   - NEEDS_IMPROVEMENT: Issues need to be addressed

The planner will review your feature requests and decide which to implement."""

    response = run_agent("user", prompt)
    return {
        "full_feedback": response,
        "satisfied": "SATISFIED" in response and "NEEDS_IMPROVEMENT" not in response
    }


def run_iteration(task: str, user_feedback: str | None = None) -> dict:
    """Run one iteration of the development loop."""
    results = {}

    # Stage 1: Planning
    print("\n[1/5] PLANNER designing solution...")
    results["planner"] = planner(task, user_feedback)
    print(f"\n{results['planner']}\n")

    # Stage 2: Implementation
    print("\n[2/5] IMPLEMENTER writing code...")
    results["implementer"] = implementer(results["planner"], task)
    print(f"\n{results['implementer']}\n")

    # Stage 3: Review
    print("\n[3/5] REVIEWER checking implementation...")
    review_result = reviewer(results["implementer"], task)
    results["reviewer"] = review_result["full_review"]
    print(f"\n{results['reviewer']}\n")

    # If reviewer says NEEDS_CHANGES, could loop back to implementer here
    # For now, we continue to get user feedback either way

    # Stage 4: Testing (with reviewer feed-forward)
    print("\n[4/5] TESTER creating tests and usage docs...")
    results["tester"] = tester(results["implementer"], task, results["reviewer"])
    print(f"\n{results['tester']}\n")

    # Stage 5: User feedback
    print("\n[5/5] USER trying the code...")
    user_result = user(results["implementer"], task, results["tester"])
    results["user"] = user_result["full_feedback"]
    results["user_satisfied"] = user_result["satisfied"]
    print(f"\n{results['user']}\n")

    return results


def run_pipeline(task: str, max_iterations: int = 3) -> dict:
    """Run the development loop with feedback iterations."""
    print("=" * 60)
    print("SUPERVISOR: Starting development loop")
    print(f"TASK: {task}")
    print(f"MAX ITERATIONS: {max_iterations}")
    print("=" * 60)

    all_results = []
    user_feedback = None

    for i in range(max_iterations):
        print(f"\n{'='*60}")
        print(f"ITERATION {i + 1} of {max_iterations}")
        print("=" * 60)

        results = run_iteration(task, user_feedback)
        all_results.append(results)

        if results["user_satisfied"]:
            print("\n" + "=" * 60)
            print("SUPERVISOR: User is SATISFIED - development complete!")
            print("=" * 60)
            break

        if i < max_iterations - 1:
            print("\n" + "-" * 60)
            print("SUPERVISOR: User requested improvements - starting next iteration")
            print("-" * 60)
            user_feedback = results["user"]
    else:
        print("\n" + "=" * 60)
        print("SUPERVISOR: Max iterations reached")
        print("=" * 60)

    return {
        "task": task,
        "iterations": len(all_results),
        "results": all_results,
        "final_satisfied": all_results[-1]["user_satisfied"] if all_results else False
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description> [--max-iterations N]")
        print(f"\nExample: {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    max_iterations = 3
    if "--max-iterations" in args:
        idx = args.index("--max-iterations")
        max_iterations = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    task = " ".join(args)
    run_pipeline(task, max_iterations)
