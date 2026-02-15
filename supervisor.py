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

Be concise and actionable. The implementer may push back on the HOW.

If you need clarification or are stuck, you can escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

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

Provide the implementation code in fenced code blocks with filenames.

If you need clarification or are stuck, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent("implementer", prompt)

    # Extract and save code blocks
    # Supports multiple formats:
    #   ```python filename.py
    #   **File: `filename.py`** followed by ```python
    #   # filename.py at start of code block
    import re

    files_created = []

    # Pattern 1: ```python filename.py\ncode```
    pattern1 = re.findall(r'```(\w+)?\s+(\S+\.(?:py|js|ts|sh|yaml|yml|json))\n(.*?)```',
                          response, re.DOTALL)
    for lang, filename, code in pattern1:
        save_artifact(filename.strip(), code.strip())
        files_created.append(filename.strip())

    # Pattern 2: **File: `filename.py`** followed by ```\ncode```
    pattern2 = re.findall(r'\*\*File:\s*`(\S+\.(?:py|js|ts|sh|yaml|yml|json))`\*\*\s*\n+```\w*\n(.*?)```',
                          response, re.DOTALL)
    for filename, code in pattern2:
        if filename not in files_created:
            save_artifact(filename.strip(), code.strip())
            files_created.append(filename.strip())

    # Pattern 3: # filename.py as first line in code block
    pattern3 = re.findall(r'```\w*\n#\s*(\S+\.(?:py|js|ts|sh|yaml|yml|json))\n(.*?)```',
                          response, re.DOTALL)
    for filename, code in pattern3:
        if filename not in files_created:
            save_artifact(filename.strip(), code.strip())
            files_created.append(filename.strip())

    # files_created is already populated above

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
4. What should the implementer know that would help future reviews?

If you need clarification or are blocked, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

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
4. Any gaps in the implementation that testing revealed?

If you need clarification or are blocked, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent("tester", prompt)

    # Extract and save test files
    import re
    # Extract test files - support multiple formats
    test_files = []

    # Pattern 1: ```python test_*.py
    pattern1 = re.findall(r'```(?:python)?\s*(test_\S+\.py)\n(.*?)```', response, re.DOTALL)
    for filename, code in pattern1:
        save_artifact(filename.strip(), code.strip())
        test_files.append(filename.strip())

    # Pattern 2: **File: `test_*.py`** followed by code block
    pattern2 = re.findall(r'\*\*File:\s*`(test_\S+\.py)`\*\*\s*\n+```\w*\n(.*?)```', response, re.DOTALL)
    for filename, code in pattern2:
        if filename.strip() not in test_files:
            save_artifact(filename.strip(), code.strip())
            test_files.append(filename.strip())

    # Save usage docs
    save_artifact("USAGE.md", f"# Usage Instructions\n\n{response}")
    git_commit("[tester] Tests and usage documentation")

    return {
        "output": response,
        "test_files": test_files
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

The planner will review your feature requests and decide which to implement.

If you are stuck or need help from a human, escalate:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent("user", prompt)

    # Save user feedback
    save_artifact("USER_FEEDBACK.md", f"# User Feedback\n\n{response}")
    git_commit("[user] User feedback and feature requests")

    return {
        "output": response,
        "satisfied": "SATISFIED" in response and "NEEDS_IMPROVEMENT" not in response
    }


def process_agent_output(agent_name: str, output: str, iteration: int) -> str:
    """Process agent output, checking for escalations."""
    escalation = check_for_escalation(output)
    if escalation:
        human_response = request_human_input(agent_name, escalation, iteration)
        return output + f"\n\n## Human Response\n\n{human_response}"
    return output


def run_iteration(task: str, iteration: int, user_feedback: str | None = None,
                  shared_understanding: str | None = None) -> dict:
    """Run one iteration of the development loop."""
    results = {}

    # Stage 1: Planning
    print(f"\n[1/5] PLANNER designing solution...")
    plan_result = planner(task, user_feedback, shared_understanding)
    results["planner"] = process_agent_output("planner", plan_result["output"], iteration)
    print(f"\n{results['planner']}\n")

    # Stage 2: Implementation
    print(f"\n[2/5] IMPLEMENTER writing code...")
    impl_result = implementer(results["planner"], task)
    results["implementer"] = process_agent_output("implementer", impl_result["output"], iteration)
    results["files_created"] = impl_result.get("files_created", [])
    print(f"\n{results['implementer']}\n")

    # Stage 3: Review
    print(f"\n[3/5] REVIEWER checking implementation...")
    review_result = reviewer(results["implementer"], task)
    results["reviewer"] = process_agent_output("reviewer", review_result["output"], iteration)
    results["approved"] = review_result["approved"]
    print(f"\n{results['reviewer']}\n")

    # Stage 4: Testing (with reviewer feed-forward)
    print(f"\n[4/5] TESTER creating tests and usage docs...")
    test_result = tester(results["implementer"], task, results["reviewer"])
    results["tester"] = process_agent_output("tester", test_result["output"], iteration)
    print(f"\n{results['tester']}\n")

    # Stage 5: User feedback
    print(f"\n[5/5] USER trying the code...")
    user_result = user(results["implementer"], task, results["tester"])
    results["user"] = process_agent_output("user", user_result["output"], iteration)
    results["user_satisfied"] = user_result["satisfied"]
    print(f"\n{results['user']}\n")

    # Create iteration understanding document - what we learned this iteration
    iteration_understanding = f"""# Iteration {iteration} Understanding

## What We Learned

### From Planner
{plan_result.get('output', '')[-2000:] if plan_result.get('output') else 'N/A'}

### From Implementer
Files created: {', '.join(results.get('files_created', [])) or 'None'}

### From Reviewer
Verdict: {'APPROVED' if results['approved'] else 'NEEDS_CHANGES'}

{results.get('reviewer', '')[-1500:]}

### From Tester
{results.get('tester', '')[-1500:]}

### From User
Verdict: {'SATISFIED' if results['user_satisfied'] else 'NEEDS_IMPROVEMENT'}

{results.get('user', '')[-1500:]}

## Summary

- Planner confidence: {plan_result.get('confidence', 'N/A')}
- Reviewer verdict: {'APPROVED' if results['approved'] else 'NEEDS_CHANGES'}
- User verdict: {'SATISFIED' if results['user_satisfied'] else 'NEEDS_IMPROVEMENT'}
"""
    save_artifact(f"ITERATION_{iteration}_UNDERSTANDING.md", iteration_understanding)

    # Create human-readable summary for review
    human_summary = f"""# Iteration {iteration} Summary - For Human Review

## Status
- **Reviewer**: {'✓ APPROVED' if results['approved'] else '✗ NEEDS_CHANGES'}
- **User**: {'✓ SATISFIED' if results['user_satisfied'] else '✗ NEEDS_IMPROVEMENT'}

## Files Created
{chr(10).join('- ' + f for f in results.get('files_created', [])) or '- None'}

## Key Decisions Made
(Extracted from agent outputs - review for accuracy)

## User Feedback & Feature Requests
{results.get('user', '')[-1000:]}

## Questions for Human Review
1. Does the implementation match your expectations?
2. Are there any constraints or context the agents missed?
3. Should any feature requests be prioritized differently?

## Next Steps
{'Development complete - ready for final review.' if results['user_satisfied'] else 'Another iteration needed - review feedback above.'}

---
*Add your comments below. They will be incorporated into the next iteration.*

## Human Comments


"""
    summary_path = save_artifact(f"ITERATION_{iteration}_HUMAN_REVIEW.md", human_summary)
    git_commit(f"[supervisor] Iteration {iteration} complete - ready for human review")

    print(f"\n{'='*60}")
    print(f"ITERATION {iteration} COMPLETE - HUMAN REVIEW REQUESTED")
    print(f"{'='*60}")
    print(f"\nReview: {summary_path}")
    print("Add comments to the 'Human Comments' section if needed.")

    return results


def load_understanding(understanding_path: str | Path) -> str:
    """Load shared understanding from a file or directory of files."""
    path = Path(understanding_path)

    if path.is_file():
        return path.read_text()

    if path.is_dir():
        # Synthesize from multiple documents
        docs = []
        for f in sorted(path.glob("*.md")):
            docs.append(f"## {f.name}\n\n{f.read_text()[:3000]}")
        return "\n\n---\n\n".join(docs)

    return ""


def check_human_comments(iteration: int) -> str | None:
    """Check if human added comments to the review document."""
    review_path = WORKSPACE / f"ITERATION_{iteration}_HUMAN_REVIEW.md"
    if not review_path.exists():
        return None

    content = review_path.read_text()
    # Look for content after "## Human Comments"
    if "## Human Comments" in content:
        comments_section = content.split("## Human Comments")[-1].strip()
        if comments_section and len(comments_section) > 10:
            return comments_section
    return None


def check_for_escalation(agent_output: str) -> dict | None:
    """Check if an agent is requesting human help."""
    escalation_markers = [
        "ESCALATE:",
        "QUESTION FOR HUMAN:",
        "NEED CLARIFICATION:",
        "STUCK:",
        "BLOCKED:",
    ]

    for marker in escalation_markers:
        if marker in agent_output.upper():
            # Extract the escalation content
            lines = agent_output.split('\n')
            escalation_lines = []
            capturing = False
            for line in lines:
                if any(m in line.upper() for m in escalation_markers):
                    capturing = True
                if capturing:
                    escalation_lines.append(line)
                    if line.strip() == "" and len(escalation_lines) > 1:
                        break
            return {
                "needs_human": True,
                "message": '\n'.join(escalation_lines)
            }
    return None


def request_human_input(agent_name: str, escalation: dict, iteration: int) -> str:
    """Request input from human when agent escalates."""
    print(f"\n{'='*60}")
    print(f"ESCALATION from {agent_name.upper()}")
    print("="*60)
    print(f"\n{escalation['message']}\n")

    # Save escalation to file
    escalation_path = WORKSPACE / f"ESCALATION_{iteration}_{agent_name}.md"
    escalation_content = f"""# Escalation from {agent_name}

## Agent's Question/Issue

{escalation['message']}

## Human Response

(Enter your response below)

"""
    escalation_path.write_text(escalation_content)

    print(f"Respond in: {escalation_path}")
    print("Or type your response below (blank line to finish):")
    print("-" * 60)

    lines = []
    while True:
        try:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
        except EOFError:
            break

    response = '\n'.join(lines)

    if response.strip():
        # Update file with response
        escalation_content += response
        escalation_path.write_text(escalation_content)
        git_commit(f"[human] Response to {agent_name} escalation")
        return response

    # Check if they edited the file instead
    content = escalation_path.read_text()
    if "## Human Response" in content:
        response = content.split("## Human Response")[-1].strip()
        if response:
            git_commit(f"[human] Response to {agent_name} escalation")
            return response

    return "(No response provided - agent should proceed with best judgment)"


def run_pipeline(task: str, max_iterations: int = 3, understanding_path: str | None = None) -> dict:
    """Run the development loop with feedback iterations."""

    # Initialize workspace with git
    init_workspace()

    # Load shared understanding if provided
    shared_understanding = None
    if understanding_path:
        shared_understanding = load_understanding(understanding_path)
        if shared_understanding:
            print(f"Loaded shared understanding from: {understanding_path}")
            # Save to workspace for reference
            save_artifact("SHARED_UNDERSTANDING.md", shared_understanding)
            git_commit("[supervisor] Import shared understanding")
        else:
            print(f"Warning: No understanding found at: {understanding_path}")

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
            print(f"SUPERVISOR: User requested improvements - continuing to iteration {iteration + 1}")
            print("-" * 60)

            # Autonomous mode: just continue with user feedback
            # Human can review checkpoints async via git history
            user_feedback = results["user"]

            # Update cumulative understanding with learnings
            cumulative_path = WORKSPACE / "CUMULATIVE_UNDERSTANDING.md"
            iteration_understanding = (WORKSPACE / f"ITERATION_{iteration}_UNDERSTANDING.md").read_text()

            if cumulative_path.exists():
                cumulative = cumulative_path.read_text()
                cumulative += f"\n\n---\n\n{iteration_understanding}"
            else:
                cumulative = f"# Cumulative Understanding\n\nLearnings accumulated across iterations.\n\n---\n\n{iteration_understanding}"

            cumulative_path.write_text(cumulative)
            git_commit(f"[supervisor] Update cumulative understanding after iteration {iteration}")
    else:
        print("\n" + "=" * 60)
        print("SUPERVISOR: Max iterations reached")
        print("=" * 60)

    # Final comprehensive summary for human review
    final_status = "COMPLETE" if all_results[-1]["user_satisfied"] else "INCOMPLETE"

    # Collect all files created
    all_files = set()
    for r in all_results:
        all_files.update(r.get('files_created', []))

    final_summary = f"""# Development Loop Complete - Human Review

## Summary

| Field | Value |
|-------|-------|
| Task | {task} |
| Status | **{final_status}** |
| Iterations | {len(all_results)} of {max_iterations} |
| Completed | {datetime.now().isoformat()} |

## Files Created

{chr(10).join('- `' + f + '`' for f in sorted(all_files)) or '- None'}

## Iteration History

"""
    for i, r in enumerate(all_results):
        iteration_num = i + 1
        final_summary += f"""### Iteration {iteration_num}

- **Reviewer**: {'✓ APPROVED' if r.get('approved') else '✗ NEEDS_CHANGES'}
- **User**: {'✓ SATISFIED' if r.get('user_satisfied') else '✗ NEEDS_IMPROVEMENT'}
- **Files**: {', '.join(r.get('files_created', [])) or 'None'}

"""

    # Include final user feedback
    if all_results:
        final_summary += f"""## Final User Feedback

{all_results[-1].get('user', 'N/A')[:2000]}

## What Was Learned

See `CUMULATIVE_UNDERSTANDING.md` for full learnings across all iterations.

## Next Steps

"""
        if all_results[-1]["user_satisfied"]:
            final_summary += """The User agent is satisfied. Human should review:
1. Generated code in workspace/
2. Test files (test_*.py)
3. Usage documentation (USAGE.md)

If changes are needed, run another iteration with feedback.
"""
        else:
            final_summary += """The User agent is NOT satisfied. Options:
1. Review the feedback above and run more iterations
2. Provide additional context/understanding
3. Manually address the remaining issues

To continue: `uv run supervisor.py --understanding workspace/ "task" --max-iterations N`
"""

    save_artifact("FINAL_REPORT.md", final_summary)
    git_commit(f"[supervisor] Task {final_status.lower()} - final report ready")

    print(f"\n{'='*60}")
    print(f"FINAL REPORT: workspace/FINAL_REPORT.md")
    print(f"{'='*60}")

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
        print(f"  --understanding PATH  Path to understanding file or directory")
        print(f"\nThe loop runs autonomously. Human reviews FINAL_REPORT.md at the end.")
        print(f"\nExamples:")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --understanding workspace/SHARED_UNDERSTANDING.md 'build the feature'")
        print(f"  {sys.argv[0]} --understanding ./context/ 'build feature'  # directory of docs")
        print(f"  {sys.argv[0]} --max-iterations 5 'complex feature'")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    max_iterations = 3
    understanding_path = None

    if "--max-iterations" in args:
        idx = args.index("--max-iterations")
        max_iterations = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if "--understanding" in args:
        idx = args.index("--understanding")
        understanding_path = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    task = " ".join(args)
    result = run_pipeline(task, max_iterations, understanding_path)

    print(f"\nWorkspace: {result['workspace']}")
    print(f"Run 'git log --oneline' in the workspace to see the commit history.")
