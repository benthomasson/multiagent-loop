#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

"""
Shared Understanding Builder - Phase 0 of the development loop.

Before the planner→implementer→reviewer→tester→user cycle begins,
humans and AI need to build shared understanding of the problem.

This phase:
1. Gathers context from available sources
2. Engages in validation dialogue
3. Identifies gaps and asks clarifying questions
4. Creates a shared understanding document

The output is a SHARED_UNDERSTANDING.md that all agents reference.

See: https://github.com/benthomasson/shared-understanding
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime

WORKSPACE = Path(__file__).parent / "workspace"

def run_claude(prompt: str, continue_session: bool = False) -> str:
    """Run claude -p with the understanding agent context."""
    # Use the workspace as the context directory for session continuity
    understand_dir = Path(__file__).parent / "agents" / "understand"
    understand_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["claude", "-p", prompt]
    if continue_session:
        cmd.append("-c")

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=understand_dir
    )
    return result.stdout.strip()


def gather_initial_context(task: str, context_sources: list[str] | None = None) -> str:
    """Gather initial context about the task."""

    context_section = ""
    if context_sources:
        context_section = "\nADDITIONAL CONTEXT PROVIDED:\n"
        for source in context_sources:
            # Check if it's a file path
            path = Path(source)
            if path.exists():
                context_section += f"\n--- {source} ---\n"
                context_section += path.read_text()[:5000]  # Limit size
                context_section += "\n"
            else:
                context_section += f"\n{source}\n"

    prompt = f"""You are helping build shared understanding of a problem before development begins.

TASK: {task}
{context_section}

Your job is to:
1. Analyze the task and identify what we know vs what we don't know
2. List assumptions that need validation
3. Identify information gaps that could cause problems later
4. Ask 3-5 clarifying questions that would improve understanding

Format your response as:

## INITIAL ANALYSIS

What we understand about this task...

## ASSUMPTIONS

- Assumption 1 (needs validation: yes/no)
- Assumption 2 ...

## INFORMATION GAPS

What information is missing that we need...

## CLARIFYING QUESTIONS

1. Question 1?
2. Question 2?
...

Be specific and practical. These questions will be answered by a human."""

    return run_claude(prompt)


def validate_understanding(task: str, initial_analysis: str, human_answers: str) -> str:
    """Validate and refine understanding based on human input."""

    prompt = f"""We are building shared understanding of a problem.

ORIGINAL TASK: {task}

INITIAL ANALYSIS:
{initial_analysis}

HUMAN ANSWERS TO QUESTIONS:
{human_answers}

Based on the human's answers:

1. Update our understanding - what new information did we learn?
2. Identify any remaining gaps or ambiguities
3. Check for contradictions between assumptions and answers
4. Summarize the validated understanding

Format your response as:

## UPDATED UNDERSTANDING

What we now understand with high confidence...

## REMAINING GAPS

What we still don't know (and whether we can proceed without it)...

## POTENTIAL RISKS

Issues that could arise based on current understanding...

## READY TO PROCEED?

- YES: Understanding is sufficient to begin development
- NO: List what else is needed

Be honest about uncertainty."""

    return run_claude(prompt, continue_session=True)


def create_shared_understanding_doc(task: str, analysis: str, validation: str) -> str:
    """Create the final shared understanding document."""

    prompt = f"""Create a final SHARED_UNDERSTANDING.md document that captures everything
we've learned about this task. This document will be used by the development team
(planner, implementer, reviewer, tester, user) as their foundation.

ORIGINAL TASK: {task}

INITIAL ANALYSIS:
{analysis}

VALIDATED UNDERSTANDING:
{validation}

Create a comprehensive but concise document with:

## Problem Statement

Clear statement of what we're solving and why

## Context

Relevant background information

## Requirements

What must be true for this to be successful

## Constraints

Limitations, boundaries, things we cannot change

## Assumptions

What we're assuming to be true (mark confidence: high/medium/low)

## Out of Scope

What we are explicitly NOT doing

## Success Criteria

How we'll know when we're done

## Open Questions

Things we don't know but will discover during development

## Key Decisions Made

Decisions that were made during understanding phase

Make this document useful for someone starting fresh."""

    return run_claude(prompt, continue_session=True)


def interactive_understanding(task: str, context_sources: list[str] | None = None):
    """Run an interactive shared understanding session."""

    WORKSPACE.mkdir(exist_ok=True)

    print("=" * 60)
    print("SHARED UNDERSTANDING - Phase 0")
    print("=" * 60)
    print(f"\nTASK: {task}\n")

    # Step 1: Initial analysis
    print("\n[1/3] Gathering initial context and analyzing task...")
    initial_analysis = gather_initial_context(task, context_sources)
    print(f"\n{initial_analysis}\n")

    # Save initial analysis
    (WORKSPACE / "INITIAL_ANALYSIS.md").write_text(
        f"# Initial Analysis\n\nTask: {task}\n\n{initial_analysis}"
    )

    # Step 2: Get human input
    print("\n" + "-" * 60)
    print("Please answer the clarifying questions above.")
    print("(You can paste multiple lines. Enter a blank line when done.)")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line == "":
                if lines:  # Only break if we have some input
                    break
            else:
                lines.append(line)
        except EOFError:
            break

    human_answers = "\n".join(lines)

    if not human_answers.strip():
        print("\nNo answers provided. Using initial analysis only.")
        human_answers = "(No additional input provided - proceeding with assumptions)"

    # Step 3: Validate understanding
    print("\n[2/3] Validating understanding based on your answers...")
    validation = validate_understanding(task, initial_analysis, human_answers)
    print(f"\n{validation}\n")

    # Save validation
    (WORKSPACE / "VALIDATION.md").write_text(
        f"# Validation\n\nHuman Answers:\n{human_answers}\n\n{validation}"
    )

    # Step 4: Create final document
    print("\n[3/3] Creating shared understanding document...")
    shared_doc = create_shared_understanding_doc(task, initial_analysis, validation)
    print(f"\n{shared_doc}\n")

    # Save final document
    doc_path = WORKSPACE / "SHARED_UNDERSTANDING.md"
    doc_path.write_text(shared_doc)

    print("=" * 60)
    print(f"Shared understanding saved to: {doc_path}")
    print("=" * 60)
    print("\nNext: Run the development loop with this understanding:")
    print(f"  uv run supervisor.py --understanding {doc_path} \"{task}\"")

    return shared_doc


def batch_understanding(task: str, answers_file: str, context_sources: list[str] | None = None):
    """Run shared understanding in batch mode with pre-provided answers."""

    WORKSPACE.mkdir(exist_ok=True)

    answers = Path(answers_file).read_text()

    print("=" * 60)
    print("SHARED UNDERSTANDING - Phase 0 (Batch Mode)")
    print("=" * 60)
    print(f"\nTASK: {task}\n")

    # Step 1: Initial analysis
    print("\n[1/3] Gathering initial context and analyzing task...")
    initial_analysis = gather_initial_context(task, context_sources)
    print(f"\n{initial_analysis}\n")

    # Step 2: Validate with provided answers
    print("\n[2/3] Validating understanding with provided answers...")
    validation = validate_understanding(task, initial_analysis, answers)
    print(f"\n{validation}\n")

    # Step 3: Create final document
    print("\n[3/3] Creating shared understanding document...")
    shared_doc = create_shared_understanding_doc(task, initial_analysis, validation)

    doc_path = WORKSPACE / "SHARED_UNDERSTANDING.md"
    doc_path.write_text(shared_doc)

    print(f"\nSaved to: {doc_path}")
    return shared_doc


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description> [--context FILE...]")
        print(f"       {sys.argv[0]} <task> --answers FILE  (batch mode)")
        print(f"\nExamples:")
        print(f"  {sys.argv[0]} 'build a REST API for user management'")
        print(f"  {sys.argv[0]} 'fix the login bug' --context JIRA-123.md slack-thread.txt")
        print(f"  {sys.argv[0]} 'new feature' --answers answers.txt")
        sys.exit(1)

    args = sys.argv[1:]

    # Parse arguments
    context_sources = []
    answers_file = None
    task_parts = []

    i = 0
    while i < len(args):
        if args[i] == "--context":
            i += 1
            while i < len(args) and not args[i].startswith("--"):
                context_sources.append(args[i])
                i += 1
        elif args[i] == "--answers":
            i += 1
            if i < len(args):
                answers_file = args[i]
                i += 1
        else:
            task_parts.append(args[i])
            i += 1

    task = " ".join(task_parts)

    if answers_file:
        batch_understanding(task, answers_file, context_sources or None)
    else:
        interactive_understanding(task, context_sources or None)
