#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Supervisor - orchestrates the multi-agent pipeline.

Pipeline stages:
1. Architect - designs the solution, breaks into tasks
2. Coder - implements each task
3. Reviewer - reviews the implementation
4. Tester - validates the implementation

Each agent maintains its own conversation context via directory isolation.
"""

import sys
from pathlib import Path
from agent import run_agent

WORKSPACE = Path(__file__).parent / "workspace"

def architect(task: str) -> str:
    """Have the architect design a solution."""
    prompt = f"""You are a software architect. Analyze this task and create a plan:

TASK: {task}

Provide:
1. A brief analysis of the requirements
2. A breakdown of implementation steps
3. Any key design decisions

Be concise and actionable."""

    return run_agent("architect", prompt)

def coder(plan: str, task: str) -> str:
    """Have the coder implement the solution."""
    prompt = f"""You are a software developer. Implement the following based on the architect's plan:

ORIGINAL TASK: {task}

ARCHITECT'S PLAN:
{plan}

Write the code. Be concise - just provide the implementation."""

    return run_agent("coder", prompt)

def reviewer(code: str, task: str) -> str:
    """Have the reviewer check the implementation."""
    prompt = f"""You are a code reviewer. Review this implementation:

ORIGINAL TASK: {task}

CODE:
{code}

Provide:
1. Is this correct? (YES/NO)
2. Any issues found
3. Suggested improvements (if any)

Be concise."""

    return run_agent("reviewer", prompt)

def tester(code: str, task: str) -> str:
    """Have the tester validate the implementation."""
    prompt = f"""You are a QA tester. Create tests for this implementation:

ORIGINAL TASK: {task}

CODE:
{code}

Provide:
1. Test cases to validate the implementation
2. Edge cases to consider
3. A simple test script if applicable

Be concise."""

    return run_agent("tester", prompt)

def run_pipeline(task: str) -> dict:
    """Run the full development pipeline."""
    results = {}

    print("=" * 60)
    print("SUPERVISOR: Starting development pipeline")
    print(f"TASK: {task}")
    print("=" * 60)

    # Stage 1: Architecture
    print("\n[1/4] ARCHITECT designing solution...")
    results["architect"] = architect(task)
    print(f"\n{results['architect']}\n")

    # Stage 2: Implementation
    print("\n[2/4] CODER implementing solution...")
    results["coder"] = coder(results["architect"], task)
    print(f"\n{results['coder']}\n")

    # Stage 3: Review
    print("\n[3/4] REVIEWER checking implementation...")
    results["reviewer"] = reviewer(results["coder"], task)
    print(f"\n{results['reviewer']}\n")

    # Stage 4: Testing
    print("\n[4/4] TESTER creating tests...")
    results["tester"] = tester(results["coder"], task)
    print(f"\n{results['tester']}\n")

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
