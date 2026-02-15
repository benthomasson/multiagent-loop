#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Supervisor - orchestrates the multi-agent development loop.

Communication Flow:
    Planner (what/why, suggests how)
        ↓ [git commit: plan]
    Implementer (controls how, can push back)
        ↓ [git commit: implementation]
    Reviewer (feedback to implementer, feed-forward to tester)
        ↓ [git commit: review]
    Tester (documents usage, provides instructions to user)
        ↓ [git commit: tests + docs]
    User (actually runs code, requests features from planner)
        ↓ [git commit: user feedback]
    [loops back to Planner]

Each stage includes self-review: "What went well? What would make my job easier?"
Git commits at each stage provide checkpoints and audit trail.

See: "Claude Is Your User" - designing software for AI as the primary user.
"""

import subprocess
import sys
import json
import os
from pathlib import Path
from datetime import datetime
from agent import run_agent

WORKSPACE = Path(__file__).parent / "workspace"

def git_commit(message: str, files: list[str] | None = None) -> bool:
    """Commit changes to git with the given message."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        # Stage files
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=WORKSPACE, env=env, capture_output=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=WORKSPACE, env=env, capture_output=True)

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=WORKSPACE, env=env, capture_output=True
        )
        if result.returncode == 0:
            # No changes staged
            return False

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=WORKSPACE, env=env, capture_output=True
        )
        return True
    except Exception as e:
        print(f"  [git commit failed: {e}]")
        return False

def init_workspace():
    """Initialize the workspace directory and git repo."""
    WORKSPACE.mkdir(exist_ok=True)
    git_dir = WORKSPACE / ".git"
    if not git_dir.exists():
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        subprocess.run(["git", "init"], cwd=WORKSPACE, env=env, capture_output=True)
        # Create initial commit
        (WORKSPACE / ".gitkeep").touch()
        subprocess.run(["git", "add", ".gitkeep"], cwd=WORKSPACE, env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initialize workspace"],
            cwd=WORKSPACE, env=env, capture_output=True
        )

def save_artifact(name: str, content: str) -> Path:
    """Save an artifact to the workspace."""
    path = WORKSPACE / name
    path.write_text(content)
    return path

def planner(task: str, user_feedback: str | None = None, shared_understanding: str | None = None) -> dict:
    """
    Planner: Product Manager + Architect
    Decides WHAT and WHY, suggests HOW.
    Receives feature requests from User and decides if they're worth implementing.
    Includes self-review.
    """
    feedback_section = ""
    if user_feedback:
        feedback_section = f"""
USER FEEDBACK FROM PREVIOUS ITERATION:
{user_feedback}

Consider this feedback. Decide which feature requests are worth implementing.
Explain which you'll address and which you won't (and why).
"""

    understanding_section = ""
    if shared_understanding:
        understanding_section = f"""
SHARED UNDERSTANDING (Phase 0):
This document was collaboratively created by humans and AI to build shared
understanding before development began. Use it as your foundation.

{shared_understanding}

---

"""

    prompt = f"""You are a software planner (product manager + architect).
You decide WHAT to build and WHY. You suggest HOW, but the implementer
has final say on implementation approach.
{understanding_section}
TASK: {task}
{feedback_section}
Provide your response in TWO parts:

## PLAN

1. Requirements analysis - what exactly needs to be built and why
2. Implementation steps (suggestions for the implementer)
3. Key design decisions
4. Success criteria - what the user should be able to do when complete
5. If addressing user feedback, explain what you're prioritizing and why

## SELF-REVIEW

After writing your plan, reflect:
1. What went well in your planning process?
2. What information were you missing that would have helped?
3. What would make your job easier next time?
4. Rate your confidence in this plan (HIGH/MEDIUM/LOW) and explain why.

Be concise and actionable. The implementer may push back on the HOW."""

    response = run_agent("planner", prompt)

    # Save plan to workspace
    save_artifact("PLAN.md", f"# Plan\n\nTask: {task}\n\n{response}")
    git_commit(f"[planner] Plan for: {task[:50]}...")

    return {
        "output": response,
        "confidence": "HIGH" if "HIGH" in response else ("LOW" if "LOW" in response else "MEDIUM")
    }


def implementer(plan: str, task: str, reviewer_feedback: str | None = None) -> dict:
    """
    Implementer: Has ultimate control of HOW.
    Can push back on planner if the suggested approach won't work.
    Includes self-review.
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
Provide your response in TWO parts:

## IMPLEMENTATION

1. If pushing back on the plan, explain WHY and what you'll do instead
2. Write the code with clear error messages and structured output
3. Save files to the current directory (they'll be committed to git)

## SELF-REVIEW

After implementing, reflect:
1. What went well in your implementation?
2. What was unclear in the plan that caused friction?
3. What would make your job easier next time?
4. Any concerns about this implementation the reviewer should focus on?

Provide the implementation code in fenced code blocks with filenames."""

    response = run_agent("implementer", prompt)

    # Extract and save code blocks
    import re
    code_blocks = re.findall(r'```(\w+)?\s*(?:#\s*)?(\S+\.(?:py|js|ts|sh|yaml|yml|json|md))\n(.*?)```',
                             response, re.DOTALL)
    files_created = []
    for lang, filename, code in code_blocks:
        # Clean filename
        filename = filename.strip()
        save_artifact(filename, code.strip())
        files_created.append(filename)

    # Also save the full response
    save_artifact("IMPLEMENTATION.md", f"# Implementation\n\n{response}")

    if files_created:
        git_commit(f"[implementer] Implement: {', '.join(files_created)}")
    else:
        git_commit(f"[implementer] Implementation notes")

    return {
        "output": response,
        "files_created": files_created
    }


def reviewer(code: str, task: str) -> dict:
    """
    Reviewer: Provides feedback to implementer AND feed-forward to tester.
    Returns structured feedback for both.
    Includes self-review.
    """
    prompt = f"""You are a code reviewer. Review this implementation and provide
feedback for two audiences.

ORIGINAL TASK: {task}

CODE:
{code}

Provide your response in THREE parts:

## FEEDBACK FOR IMPLEMENTER

- Correctness: Does it fulfill the task?
- Error handling: Are errors clear and actionable?
- Usability: Can users easily understand failures?
- Verdict: APPROVED or NEEDS_CHANGES
- If NEEDS_CHANGES, list specific changes required

## FEED-FORWARD FOR TESTER

- Key behaviors to test
- Edge cases to consider
- Suggested test scenarios
- Any areas of concern to focus testing on

## SELF-REVIEW

After reviewing, reflect:
1. What aspects of this code were easy to review? Why?
2. What made review difficult? (unclear code, missing docs, etc.)
3. What would make your job easier next time?
4. What should the implementer know that would help future reviews?"""

    response = run_agent("reviewer", prompt)

    # Save review
    save_artifact("REVIEW.md", f"# Code Review\n\n{response}")
    git_commit("[reviewer] Code review complete")

    return {
        "output": response,
        "approved": "APPROVED" in response and "NEEDS_CHANGES" not in response
    }


def tester(code: str, task: str, reviewer_notes: str) -> dict:
    """
    Tester: Documents how to use the software.
    Provides usage instructions to the User agent.
    Includes self-review.
    """
    prompt = f"""You are a QA tester. Your job is to:
1. Create tests for this implementation
2. Document HOW TO USE the software for the User

ORIGINAL TASK: {task}

CODE:
{code}

REVIEWER'S NOTES FOR TESTING:
{reviewer_notes}

Provide your response in THREE parts:

## TEST CASES

- Tests that validate the implementation
- Edge cases based on reviewer notes
- A test script if applicable (save as test_*.py)

## USAGE INSTRUCTIONS FOR USER

- Clear step-by-step instructions on how to use this software
- Example commands or function calls
- Expected outputs
- Common error scenarios and what they mean

The User will follow your instructions to actually run the software.
Make the instructions clear enough for someone (human or AI) to follow.

## SELF-REVIEW

After testing and documenting, reflect:
1. What was easy to test? What was hard?
2. What information was missing that would have helped?
3. What would make your job easier next time?
4. Any gaps in the implementation that testing revealed?"""

    response = run_agent("tester", prompt)

    # Extract and save test files
    import re
    test_blocks = re.findall(r'```(?:python)?\s*(test_\S+\.py)\n(.*?)```', response, re.DOTALL)
    for filename, code in test_blocks:
        save_artifact(filename.strip(), code.strip())

    # Save usage docs
    save_artifact("USAGE.md", f"# Usage Instructions\n\n{response}")
    git_commit("[tester] Tests and usage documentation")

    return {
        "output": response,
        "test_files": [f[0] for f in test_blocks]
    }


def user(code: str, task: str, usage_instructions: str) -> dict:
    """
    User: Actually runs the code following tester's instructions.
    Provides feature requests back to Planner.
    Includes self-review.
    """
    prompt = f"""You are a user of this software. Your job is to ACTUALLY USE it
by following the tester's instructions, then provide feedback.

ORIGINAL TASK: {task}

CODE:
{code}

USAGE INSTRUCTIONS FROM TESTER:
{usage_instructions}

Follow the instructions and try to accomplish the task.

Provide your response in THREE parts:

## USAGE REPORT

- What worked
- What failed or was confusing
- What information was missing from error messages
- Actual output you observed (if you ran the code)

## FEATURE REQUESTS

What changes would make your job easier? Be specific and practical.
Think about:
- What frustrated you?
- What information were you missing?
- What capabilities did you wish you had?

Prioritize your requests: P0 (critical), P1 (important), P2 (nice to have)

## OVERALL VERDICT

- SATISFIED: The software works well enough for the task
- NEEDS_IMPROVEMENT: Issues need to be addressed before this is usable

Explain your verdict.

The planner will review your feature requests and decide which to implement."""

    response = run_agent("user", prompt)

    # Save user feedback
    save_artifact("USER_FEEDBACK.md", f"# User Feedback\n\n{response}")
    git_commit("[user] User feedback and feature requests")

    return {
        "output": response,
        "satisfied": "SATISFIED" in response and "NEEDS_IMPROVEMENT" not in response
    }


def run_iteration(task: str, iteration: int, user_feedback: str | None = None,
                  shared_understanding: str | None = None) -> dict:
    """Run one iteration of the development loop."""
    results = {}

    # Stage 1: Planning
    print(f"\n[1/5] PLANNER designing solution...")
    plan_result = planner(task, user_feedback, shared_understanding)
    results["planner"] = plan_result["output"]
    print(f"\n{results['planner']}\n")

    # Stage 2: Implementation
    print(f"\n[2/5] IMPLEMENTER writing code...")
    impl_result = implementer(results["planner"], task)
    results["implementer"] = impl_result["output"]
    results["files_created"] = impl_result.get("files_created", [])
    print(f"\n{results['implementer']}\n")

    # Stage 3: Review
    print(f"\n[3/5] REVIEWER checking implementation...")
    review_result = reviewer(results["implementer"], task)
    results["reviewer"] = review_result["output"]
    results["approved"] = review_result["approved"]
    print(f"\n{results['reviewer']}\n")

    # Stage 4: Testing (with reviewer feed-forward)
    print(f"\n[4/5] TESTER creating tests and usage docs...")
    test_result = tester(results["implementer"], task, results["reviewer"])
    results["tester"] = test_result["output"]
    print(f"\n{results['tester']}\n")

    # Stage 5: User feedback
    print(f"\n[5/5] USER trying the code...")
    user_result = user(results["implementer"], task, results["tester"])
    results["user"] = user_result["output"]
    results["user_satisfied"] = user_result["satisfied"]
    print(f"\n{results['user']}\n")

    # Create iteration summary commit
    summary = f"""Iteration {iteration} complete

Planner confidence: {plan_result.get('confidence', 'N/A')}
Files created: {', '.join(results.get('files_created', [])) or 'None'}
Reviewer verdict: {'APPROVED' if results['approved'] else 'NEEDS_CHANGES'}
User verdict: {'SATISFIED' if results['user_satisfied'] else 'NEEDS_IMPROVEMENT'}
"""
    save_artifact(f"ITERATION_{iteration}_SUMMARY.md", summary)
    git_commit(f"[supervisor] Iteration {iteration} complete")

    return results


def run_pipeline(task: str, max_iterations: int = 3, understanding_file: str | None = None) -> dict:
    """Run the development loop with feedback iterations."""

    # Initialize workspace with git
    init_workspace()

    # Load shared understanding if provided
    shared_understanding = None
    if understanding_file:
        understanding_path = Path(understanding_file)
        if understanding_path.exists():
            shared_understanding = understanding_path.read_text()
            print(f"Loaded shared understanding from: {understanding_file}")
        else:
            print(f"Warning: Understanding file not found: {understanding_file}")

    print("=" * 60)
    print("SUPERVISOR: Starting development loop")
    print(f"TASK: {task}")
    print(f"MAX ITERATIONS: {max_iterations}")
    print(f"WORKSPACE: {WORKSPACE}")
    print("=" * 60)

    # Save task to workspace
    save_artifact("TASK.md", f"# Task\n\n{task}\n\nStarted: {datetime.now().isoformat()}")
    git_commit(f"[supervisor] Start task: {task[:50]}...")

    all_results = []
    user_feedback = None

    for i in range(max_iterations):
        iteration = i + 1
        print(f"\n{'='*60}")
        print(f"ITERATION {iteration} of {max_iterations}")
        print("=" * 60)

        results = run_iteration(task, iteration, user_feedback, shared_understanding)
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

    # Final summary
    final_status = "COMPLETE" if all_results[-1]["user_satisfied"] else "INCOMPLETE"
    final_summary = f"""# Development Loop Complete

Task: {task}
Status: {final_status}
Iterations: {len(all_results)} of {max_iterations}
Completed: {datetime.now().isoformat()}

## Iteration History

"""
    for i, r in enumerate(all_results):
        final_summary += f"### Iteration {i+1}\n"
        final_summary += f"- Approved: {r.get('approved', 'N/A')}\n"
        final_summary += f"- User Satisfied: {r.get('user_satisfied', 'N/A')}\n\n"

    save_artifact("FINAL_SUMMARY.md", final_summary)
    git_commit(f"[supervisor] Task {final_status.lower()}")

    return {
        "task": task,
        "iterations": len(all_results),
        "results": all_results,
        "final_satisfied": all_results[-1]["user_satisfied"] if all_results else False,
        "workspace": str(WORKSPACE)
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description> [options]")
        print(f"\nOptions:")
        print(f"  --max-iterations N    Maximum development iterations (default: 3)")
        print(f"  --understanding FILE  Path to shared understanding document")
        print(f"\nExamples:")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --understanding workspace/SHARED_UNDERSTANDING.md 'build the feature'")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    max_iterations = 3
    understanding_file = None

    if "--max-iterations" in args:
        idx = args.index("--max-iterations")
        max_iterations = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if "--understanding" in args:
        idx = args.index("--understanding")
        understanding_file = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    task = " ".join(args)
    result = run_pipeline(task, max_iterations, understanding_file)

    print(f"\nWorkspace: {result['workspace']}")
    print(f"Run 'git log --oneline' in the workspace to see the commit history.")
