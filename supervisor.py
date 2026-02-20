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
from agent import (
    run_agent, finalize_agent, log, log_separator, LOG_FILE,
    get_workspace_dir, get_agents_dir, set_workspace, get_workspace_name,
    DEFAULT_WORKSPACE
)

import time

# Queue file handling for continuous mode
DEFAULT_QUEUE_PATH = Path("queue.txt")

def read_queue(queue_path: Path) -> list[str]:
    """Read all tasks from the queue file. Returns empty list if file doesn't exist."""
    if not queue_path.exists():
        return []
    content = queue_path.read_text().strip()
    if not content:
        return []
    return [line.strip() for line in content.split('\n') if line.strip()]


def pop_task_from_queue(queue_path: Path) -> str | None:
    """Read and remove the first task from the queue file. Returns None if empty."""
    tasks = read_queue(queue_path)
    if not tasks:
        return None

    # Get first task
    task = tasks[0]

    # Write remaining tasks back
    remaining = tasks[1:]
    if remaining:
        queue_path.write_text('\n'.join(remaining) + '\n')
    else:
        queue_path.write_text('')

    return task


def git_commit(message: str, files: list[str] | None = None) -> bool:
    """Commit changes to git with the given message."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    try:
        # Stage files
        if files:
            for f in files:
                subprocess.run(["git", "add", f], cwd=get_workspace_dir(), env=env, capture_output=True)
        else:
            subprocess.run(["git", "add", "-A"], cwd=get_workspace_dir(), env=env, capture_output=True)

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=get_workspace_dir(), env=env, capture_output=True
        )
        if result.returncode == 0:
            # No changes staged
            return False

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=get_workspace_dir(), env=env, capture_output=True
        )
        return True
    except Exception as e:
        print(f"  [git commit failed: {e}]")
        return False

def init_workspace():
    """Initialize the workspace directory, agents directory, and git repo."""
    get_workspace_dir().mkdir(parents=True, exist_ok=True)
    # Pre-create agents directory to ensure it exists before any agent runs
    get_agents_dir().mkdir(parents=True, exist_ok=True)
    git_dir = get_workspace_dir() / ".git"
    if not git_dir.exists():
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        subprocess.run(["git", "init"], cwd=get_workspace_dir(), env=env, capture_output=True)
        # Create initial commit
        (get_workspace_dir() / ".gitkeep").touch()
        subprocess.run(["git", "add", ".gitkeep"], cwd=get_workspace_dir(), env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Initialize workspace"],
            cwd=get_workspace_dir(), env=env, capture_output=True
        )


def init_workspace_from(source: str) -> bool:
    """Initialize a workspace by cloning from a git repository.

    Accepts either a local path or a git URL. Clones the repo into the workspace
    directory, preserving git history and remote configuration for pushing back.

    Returns True if successful, False otherwise.
    """
    workspace = get_workspace_dir()
    agents_dir = get_agents_dir()

    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    # Check if workspace already exists
    if workspace.exists() and any(workspace.iterdir()):
        existing = list(workspace.iterdir())
        non_meta = [f for f in existing if f.name not in ['.git', '.gitkeep']]
        if non_meta:
            print(f"Error: Workspace '{get_workspace_name()}' already has content.")
            print(f"  Location: {workspace}")
            print(f"  Files: {[f.name for f in non_meta[:5]]}")
            return False

    # Ensure parent directories exist
    workspace.parent.mkdir(parents=True, exist_ok=True)
    agents_dir.mkdir(parents=True, exist_ok=True)

    # Determine if source is a URL or local path
    source_str = str(source)
    is_url = source_str.startswith(('git@', 'https://', 'http://', 'ssh://'))

    if not is_url:
        # Local path - convert to absolute and check it exists
        source_path = Path(source).expanduser().resolve()
        if not source_path.exists():
            print(f"Error: Source path does not exist: {source_path}")
            return False
        # Check for regular repo (.git dir) or bare repo (HEAD file directly)
        is_git_repo = (source_path / ".git").exists() or (source_path / "HEAD").exists()
        if not is_git_repo:
            print(f"Error: Source path is not a git repository: {source_path}")
            return False
        source_str = str(source_path)

    print(f"Cloning {source_str} to workspace '{get_workspace_name()}'...")

    # Clone the repository
    result = subprocess.run(
        ["git", "clone", source_str, str(workspace)],
        env=env, capture_output=True, text=True
    )

    if result.returncode != 0:
        print(f"Error: git clone failed: {result.stderr}")
        return False

    # Create a working branch for multiagent-loop work
    subprocess.run(
        ["git", "checkout", "-b", "multiagent-work"],
        cwd=workspace, env=env, capture_output=True
    )

    print(f"Workspace '{get_workspace_name()}' cloned from {source_str}")
    print(f"  Location: {workspace}")
    print(f"  Branch: multiagent-work")
    print(f"  Use --push to push changes back when done")
    return True


def push_workspace(branch: str = "main", create_pr: bool = False, squash: bool = True) -> bool:
    """Push workspace changes back to the remote repository.

    Cleans up artifact files, squashes commits, and pushes.
    Optionally creates a pull request instead of pushing directly.

    Returns True if successful, False otherwise.
    """
    workspace = get_workspace_dir()
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    if not workspace.exists() or not (workspace / ".git").exists():
        print(f"Error: Workspace '{get_workspace_name()}' is not a git repository")
        return False

    # Artifact files/directories to remove before pushing
    ARTIFACT_PATTERNS = [
        "TASK.md", "PLAN.md", "IMPLEMENTATION.md", "REVIEW.md", "USAGE.md",
        "USER_FEEDBACK.md", "FINAL_REPORT.md", "CUMULATIVE_UNDERSTANDING.md",
        "ITERATION_*.md", "planner/", "implementer/", "reviewer/", "tester/", "user/"
    ]

    # Remove artifact files
    print("Cleaning up artifact files...")
    import glob
    for pattern in ARTIFACT_PATTERNS:
        for path in glob.glob(str(workspace / pattern)):
            p = Path(path)
            if p.is_dir():
                import shutil
                shutil.rmtree(p)
                subprocess.run(["git", "rm", "-rf", str(p.relative_to(workspace))],
                             cwd=workspace, env=env, capture_output=True)
            elif p.exists():
                p.unlink()
                subprocess.run(["git", "rm", "-f", str(p.relative_to(workspace))],
                             cwd=workspace, env=env, capture_output=True)

    # Check for any uncommitted changes (including deletions)
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=workspace, env=env, capture_output=True, text=True
    )
    if result.stdout.strip():
        subprocess.run(["git", "add", "-A"], cwd=workspace, env=env, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "[multiagent-loop] Clean up artifacts"],
            cwd=workspace, env=env, capture_output=True
        )

    # Get current branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=workspace, env=env, capture_output=True, text=True
    )
    current_branch = result.stdout.strip()

    # Find the original commit before multiagent-loop started
    result = subprocess.run(
        ["git", "log", "--oneline", f"origin/{branch}..HEAD"],
        cwd=workspace, env=env, capture_output=True, text=True
    )
    commit_count = len([l for l in result.stdout.strip().split('\n') if l])

    if squash and commit_count > 1:
        print(f"Squashing {commit_count} commits...")
        # Get the commit message from the task
        task_file = workspace / "TASK.md"
        if task_file.exists():
            task_desc = task_file.read_text().strip()[:200]
        else:
            task_desc = "multiagent-loop changes"

        # Soft reset to origin and recommit
        subprocess.run(
            ["git", "reset", "--soft", f"origin/{branch}"],
            cwd=workspace, env=env, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-m", f"{task_desc}\n\nCo-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"],
            cwd=workspace, env=env, capture_output=True
        )

    if create_pr:
        # Push the working branch and create a PR
        print(f"Pushing {current_branch} branch...")
        result = subprocess.run(
            ["git", "push", "-u", "origin", current_branch],
            cwd=workspace, env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error pushing: {result.stderr}")
            return False

        print(f"Creating pull request...")
        result = subprocess.run(
            ["gh", "pr", "create", "--fill", "--base", branch],
            cwd=workspace, env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error creating PR: {result.stderr}")
            print("You can create the PR manually or push directly with --push")
            return False

        print(f"Pull request created: {result.stdout.strip()}")
        return True
    else:
        # Merge into target branch and push directly
        print(f"Merging {current_branch} into {branch}...")
        subprocess.run(["git", "checkout", branch], cwd=workspace, env=env, capture_output=True)
        result = subprocess.run(
            ["git", "merge", current_branch, "--no-edit"],
            cwd=workspace, env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error merging: {result.stderr}")
            return False

        print(f"Pushing to origin/{branch}...")
        result = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=workspace, env=env, capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"Error pushing: {result.stderr}")
            return False

        print(f"Successfully pushed to origin/{branch}")
        return True


def save_artifact(name: str, content: str) -> Path:
    """Save an artifact to the workspace."""
    path = get_workspace_dir() / name
    path.write_text(content)
    return path

def planner(task: str, user_feedback: str | None = None, shared_understanding: str | None = None,
            iteration: int = 1, continue_conversations: bool = False) -> dict:
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

    response = run_agent("planner", prompt, continue_session=(continue_conversations or iteration > 1))

    # Save plan to workspace
    save_artifact("PLAN.md", f"# Plan\n\nTask: {task}\n\n{response}")
    git_commit(f"[planner] Plan for: {task[:50]}...")

    return {
        "output": response,
        "confidence": "HIGH" if "HIGH" in response else ("LOW" if "LOW" in response else "MEDIUM")
    }


def implementer(plan: str, task: str, reviewer_feedback: str | None = None,
                iteration: int = 1, continue_conversations: bool = False) -> dict:
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

You have access to Read, Glob, Grep, Write, and Edit tools.

IMPORTANT - How to modify code:
- To MODIFY EXISTING FILES: First use Read to read the file, then use the EDIT TOOL to make changes
- To CREATE NEW FILES: Use the Write tool
- ALWAYS read existing files before editing them
- The Edit tool replaces specific text - provide exact old_string and new_string

ORIGINAL TASK: {task}

PLANNER'S PLAN:
{plan}
{feedback_section}
Provide your response in TWO parts:

## IMPLEMENTATION

1. If pushing back on the plan, explain WHY and what you'll do instead
2. For EXISTING files: Use Read to examine them, then Edit to modify them
3. For NEW files: Use Write to create them
4. Do NOT just output code in markdown - actually use the tools to modify/create files
5. Write code with clear error messages and structured output

## SELF-REVIEW

After implementing, reflect:
1. What went well in your implementation?
2. What was unclear in the plan that caused friction?
3. What would make your job easier next time?
4. Any concerns about this implementation the reviewer should focus on?

Use the Edit and Write tools to actually modify/create files - do not just output code in markdown.

If you need clarification or are stuck, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent("implementer", prompt, continue_session=(continue_conversations or iteration > 1))

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


def reviewer(code: str, task: str, iteration: int = 1, continue_conversations: bool = False) -> dict:
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

    response = run_agent("reviewer", prompt, continue_session=(continue_conversations or iteration > 1))

    # Save review
    save_artifact("REVIEW.md", f"# Code Review\n\n{response}")
    git_commit("[reviewer] Code review complete")

    return {
        "output": response,
        "approved": "APPROVED" in response and "NEEDS_CHANGES" not in response
    }


def tester(code: str, task: str, reviewer_notes: str, iteration: int = 1,
           continue_conversations: bool = False) -> dict:
    """
    Tester: Documents how to use the software.
    Provides usage instructions to the User agent.
    Includes self-review.
    """
    prompt = f"""You are a QA tester. Your job is to:
1. Create tests for this implementation
2. Document HOW TO USE the software for the User

You have access to Write, Edit, Read, Glob, Grep, and Bash tools.
USE THE WRITE TOOL to create test files.
USE BASH to run the tests and verify they pass.

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

## TEST VERDICT

After running tests, provide ONE of:
- TESTS_PASSED: All tests pass, implementation is correct
- TESTS_FAILED: Tests fail or reveal bugs that need fixing

If TESTS_FAILED, clearly describe what needs to be fixed so the implementer can address it.

## SELF-REVIEW

After testing and documenting, reflect:
1. What was easy to test? What was hard?
2. What information was missing that would have helped?
3. What would make your job easier next time?
4. Any gaps in the implementation that testing revealed?

If you need clarification or are blocked, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent("tester", prompt, continue_session=(continue_conversations or iteration > 1))

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

    # Determine if tests passed
    tests_passed = "TESTS_PASSED" in response and "TESTS_FAILED" not in response

    return {
        "output": response,
        "test_files": test_files,
        "tests_passed": tests_passed
    }


def user(code: str, task: str, usage_instructions: str, iteration: int = 1,
         continue_conversations: bool = False) -> dict:
    """
    User: Actually runs the code following tester's instructions.
    Provides feature requests back to Planner.
    Includes self-review.
    """
    prompt = f"""You are a user of this software. Your job is to ACTUALLY USE it
by following the tester's instructions, then provide feedback.

You have access to Read, Glob, Grep, and Bash tools.
USE BASH to actually run the code and observe the output.
Report what actually happened, not what you think would happen.

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

    response = run_agent("user", prompt, continue_session=(continue_conversations or iteration > 1))

    # Save user feedback
    save_artifact("USER_FEEDBACK.md", f"# User Feedback\n\n{response}")
    git_commit("[user] User feedback and feature requests")

    return {
        "output": response,
        "satisfied": "SATISFIED" in response and "NEEDS_IMPROVEMENT" not in response
    }


def process_agent_output(agent_name: str, output: str, iteration: int) -> str:
    """Process agent output, checking for escalations, then merge to main."""
    escalation = check_for_escalation(output)
    if escalation:
        human_response = request_human_input(agent_name, escalation, iteration)
        output += f"\n\n## Human Response\n\n{human_response}"

    # Merge agent's branch back to main
    if finalize_agent(agent_name):
        print(f"  [Merged {agent_name} branch to main]")

    return output


def run_iteration(task: str, iteration: int, user_feedback: str | None = None,
                  shared_understanding: str | None = None,
                  continue_conversations: bool = False,
                  max_inner_iterations: int = 3) -> dict:
    """Run one iteration of the development loop.

    Inner loops:
    - Reviewer → Implementer (if NEEDS_CHANGES)
    - Tester → Implementer (if tests fail)
    """
    results = {}

    # Stage 1: Planning
    print(f"\n[1/5] PLANNER designing solution...")
    plan_result = planner(task, user_feedback, shared_understanding, iteration, continue_conversations)
    results["planner"] = process_agent_output("planner", plan_result["output"], iteration)
    print(f"\n{results['planner']}\n")

    # Stage 2 & 3: Implementation + Review loop
    reviewer_feedback = None
    inner_iteration = 0

    while inner_iteration < max_inner_iterations:
        inner_iteration += 1

        # Implementation
        if inner_iteration == 1:
            print(f"\n[2/5] IMPLEMENTER writing code...")
        else:
            print(f"\n[2/5] IMPLEMENTER fixing issues (attempt {inner_iteration})...")

        impl_result = implementer(results["planner"], task, reviewer_feedback, iteration, continue_conversations or inner_iteration > 1)
        results["implementer"] = process_agent_output("implementer", impl_result["output"], iteration)
        results["files_created"] = impl_result.get("files_created", [])
        print(f"\n{results['implementer']}\n")

        # Review
        print(f"\n[3/5] REVIEWER checking implementation...")
        review_result = reviewer(results["implementer"], task, iteration, continue_conversations or inner_iteration > 1)
        results["reviewer"] = process_agent_output("reviewer", review_result["output"], iteration)
        results["approved"] = review_result["approved"]
        print(f"\n{results['reviewer']}\n")

        if review_result["approved"]:
            print(f"  [Reviewer APPROVED - proceeding to tester]")
            break
        else:
            print(f"  [Reviewer requested CHANGES - looping back to implementer]")
            reviewer_feedback = results["reviewer"]

    # Stage 4: Testing (with potential loop back to implementer)
    tester_iteration = 0
    tester_feedback = None

    while tester_iteration < max_inner_iterations:
        tester_iteration += 1

        if tester_iteration == 1:
            print(f"\n[4/5] TESTER creating tests and usage docs...")
        else:
            # Re-run implementer with tester feedback
            print(f"\n[2/5] IMPLEMENTER fixing test failures (attempt {tester_iteration})...")
            impl_result = implementer(results["planner"], task, tester_feedback, iteration, True)
            results["implementer"] = process_agent_output("implementer", impl_result["output"], iteration)
            results["files_created"] = impl_result.get("files_created", [])
            print(f"\n{results['implementer']}\n")

            print(f"\n[4/5] TESTER re-running tests...")

        test_result = tester(results["implementer"], task, results["reviewer"], iteration, continue_conversations or tester_iteration > 1)
        results["tester"] = process_agent_output("tester", test_result["output"], iteration)
        results["tests_passed"] = test_result.get("tests_passed", True)
        print(f"\n{results['tester']}\n")

        if results["tests_passed"]:
            print(f"  [Tests passed - proceeding to user]")
            break
        else:
            print(f"  [Tests failed - looping back to implementer]")
            tester_feedback = f"TESTER FEEDBACK (tests failed):\n{results['tester']}"

    # Stage 5: User feedback
    print(f"\n[5/5] USER trying the code...")
    user_result = user(results["implementer"], task, results["tester"], iteration, continue_conversations)
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
    review_path = get_workspace_dir() / f"ITERATION_{iteration}_HUMAN_REVIEW.md"
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
    escalation_path = get_workspace_dir() / f"ESCALATION_{iteration}_{agent_name}.md"
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


def run_pipeline(task: str, max_iterations: int = 3, understanding_path: str | None = None,
                 continue_conversations: bool = False) -> dict:
    """Run the development loop with feedback iterations."""

    # Start new log session
    log_separator(f"PIPELINE: {task[:50]}")
    log(f"Task: {task}")
    log(f"Max iterations: {max_iterations}")
    log(f"Continue conversations: {continue_conversations}")
    log(f"Understanding path: {understanding_path}")
    log(f"Log file: {LOG_FILE}")

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
    print(f"get_workspace_dir(): {get_workspace_dir()}")
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

        results = run_iteration(task, iteration, user_feedback, shared_understanding, continue_conversations)
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
            cumulative_path = get_workspace_dir() / "CUMULATIVE_UNDERSTANDING.md"
            iteration_understanding = (get_workspace_dir() / f"ITERATION_{iteration}_UNDERSTANDING.md").read_text()

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
        "workspace": str(get_workspace_dir())
    }


def run_continuous(queue_path: Path, max_iterations: int = 3,
                   understanding_path: str | None = None,
                   continue_conversations: bool = False) -> None:
    """Run the pipeline continuously, processing tasks from a queue file.

    Loops forever until interrupted with Ctrl+C. When the queue is empty,
    sleeps for 60 seconds then checks again.
    """
    print("=" * 60)
    print("SUPERVISOR: Starting continuous mode")
    print(f"Queue file: {queue_path}")
    print(f"Max iterations per task: {max_iterations}")
    print("Press Ctrl+C to stop")
    print("=" * 60)

    tasks_completed = 0

    try:
        while True:
            task = pop_task_from_queue(queue_path)

            if task:
                tasks_completed += 1
                print(f"\n{'='*60}")
                print(f"CONTINUOUS MODE: Processing task {tasks_completed}")
                print(f"Task: {task}")
                print("=" * 60)

                log_separator(f"CONTINUOUS TASK {tasks_completed}: {task[:50]}")

                try:
                    result = run_pipeline(
                        task=task,
                        max_iterations=max_iterations,
                        understanding_path=understanding_path,
                        continue_conversations=continue_conversations
                    )

                    status = "SATISFIED" if result["final_satisfied"] else "INCOMPLETE"
                    print(f"\n[Continuous] Task {tasks_completed} finished: {status}")
                    print(f"[Continuous] Iterations: {result['iterations']}")

                except Exception as e:
                    print(f"\n[Continuous] Task {tasks_completed} failed with error: {e}")
                    log(f"ERROR in task {tasks_completed}: {e}")

                # Check remaining tasks
                remaining = read_queue(queue_path)
                print(f"[Continuous] Remaining tasks in queue: {len(remaining)}")

            else:
                print(f"\n[Continuous] Queue empty. Sleeping 60 seconds... (Ctrl+C to exit)")
                time.sleep(60)

    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print("SUPERVISOR: Continuous mode stopped by user")
        print(f"Tasks completed: {tasks_completed}")
        print("=" * 60)


if __name__ == "__main__":
    # Handle --help / -h explicitly to prevent it being treated as a task
    if "-h" in sys.argv or "--help" in sys.argv:
        print(f"Usage: {sys.argv[0]} <task description> [options]")
        print(f"       {sys.argv[0]} --continuous [options]")
        print(f"\nOptions:")
        print(f"  -h, --help            Show this help message and exit")
        print(f"  --workspace NAME      Named workspace (default: 'default')")
        print(f"  --max-iterations N    Maximum development iterations (default: 3)")
        print(f"  --understanding PATH  Path to understanding file or directory")
        print(f"  --continue            Continue previous agent conversations (for follow-up runs)")
        print(f"  --continuous          Run in continuous mode, processing tasks from a queue file")
        print(f"  --queue PATH          Path to queue file (default: queue.txt)")
        print(f"  --init-from PATH|URL  Clone repo into workspace (local path or git URL)")
        print(f"  --push                Push workspace changes back to origin (then exit)")
        print(f"  --pr                  Create a pull request instead of pushing directly")
        print(f"  --no-squash           Don't squash commits when pushing (default: squash)")
        print(f"\nThe loop runs autonomously. Human reviews FINAL_REPORT.md at the end.")
        print(f"\nExamples:")
        print(f"  {sys.argv[0]} --workspace iris --init-from /path/to/iris  # Clone local repo")
        print(f"  {sys.argv[0]} --workspace iris --init-from git@github.com:user/repo.git")
        print(f"  {sys.argv[0]} --workspace iris 'add a new feature'        # Work on it")
        print(f"  {sys.argv[0]} --workspace iris --push                     # Push changes back")
        print(f"  {sys.argv[0]} --workspace iris --pr                       # Create a PR instead")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --max-iterations 5 'complex feature'")
        print(f"  {sys.argv[0]} --continue 'fix the bug identified in the last run'")
        print(f"\nContinuous mode:")
        print(f"  {sys.argv[0]} --continuous")
        print(f"  {sys.argv[0]} --continuous --queue my_tasks.txt")
        sys.exit(0)

    # Check for --continuous flag first since it doesn't require a task argument
    has_continuous = "--continuous" in sys.argv

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description> [options]")
        print(f"       {sys.argv[0]} --continuous [options]")
        print(f"\nOptions:")
        print(f"  --workspace NAME      Named workspace (default: 'default')")
        print(f"  --max-iterations N    Maximum development iterations (default: 3)")
        print(f"  --understanding PATH  Path to understanding file or directory")
        print(f"  --continue            Continue previous agent conversations (for follow-up runs)")
        print(f"  --continuous          Run in continuous mode, processing tasks from a queue file")
        print(f"  --queue PATH          Path to queue file (default: queue.txt)")
        print(f"  --init-from PATH|URL  Clone repo into workspace (local path or git URL)")
        print(f"  --push                Push workspace changes back to origin (then exit)")
        print(f"  --pr                  Create a pull request instead of pushing directly")
        print(f"  --no-squash           Don't squash commits when pushing (default: squash)")
        print(f"\nThe loop runs autonomously. Human reviews FINAL_REPORT.md at the end.")
        print(f"\nExamples:")
        print(f"  {sys.argv[0]} --workspace iris --init-from /path/to/iris  # Initialize workspace")
        print(f"  {sys.argv[0]} --workspace iris 'add a new feature'        # Work on it")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --workspace myproject 'add a new feature'")
        print(f"  {sys.argv[0]} --understanding workspace/SHARED_UNDERSTANDING.md 'build the feature'")
        print(f"  {sys.argv[0]} --understanding ./context/ 'build feature'  # directory of docs")
        print(f"  {sys.argv[0]} --max-iterations 5 'complex feature'")
        print(f"  {sys.argv[0]} --continue 'fix the bug identified in the last run'")
        print(f"\nContinuous mode:")
        print(f"  {sys.argv[0]} --continuous")
        print(f"  {sys.argv[0]} --continuous --queue my_tasks.txt")
        print(f"  {sys.argv[0]} --continuous --max-iterations 5")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    max_iterations = 3
    understanding_path = None
    continue_conversations = False
    continuous_mode = False
    queue_path = DEFAULT_QUEUE_PATH
    workspace_name = DEFAULT_WORKSPACE

    if "--workspace" in args:
        idx = args.index("--workspace")
        workspace_name = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    # Set the workspace before any other operations
    set_workspace(workspace_name)

    # Handle --init-from early (it exits after completing)
    if "--init-from" in args:
        idx = args.index("--init-from")
        source = args[idx + 1]  # Can be path or URL
        args = args[:idx] + args[idx + 2:]
        success = init_workspace_from(source)
        sys.exit(0 if success else 1)

    # Handle --push and --pr early (they exit after completing)
    if "--push" in args or "--pr" in args:
        create_pr = "--pr" in args
        squash = "--no-squash" not in args
        if "--push" in args:
            args.remove("--push")
        if "--pr" in args:
            args.remove("--pr")
        if "--no-squash" in args:
            args.remove("--no-squash")
        success = push_workspace(branch="main", create_pr=create_pr, squash=squash)
        sys.exit(0 if success else 1)

    if "--max-iterations" in args:
        idx = args.index("--max-iterations")
        max_iterations = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if "--understanding" in args:
        idx = args.index("--understanding")
        understanding_path = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    if "--continue" in args:
        idx = args.index("--continue")
        continue_conversations = True
        args = args[:idx] + args[idx + 1:]

    if "--continuous" in args:
        idx = args.index("--continuous")
        continuous_mode = True
        args = args[:idx] + args[idx + 1:]

    if "--queue" in args:
        idx = args.index("--queue")
        queue_path = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    if continuous_mode:
        # Run in continuous mode
        run_continuous(
            queue_path=queue_path,
            max_iterations=max_iterations,
            understanding_path=understanding_path,
            continue_conversations=continue_conversations
        )
    else:
        # Run single task
        task = " ".join(args)
        if not task:
            print("Error: No task specified. Use --continuous for queue mode or provide a task.")
            sys.exit(1)

        result = run_pipeline(task, max_iterations, understanding_path, continue_conversations)

        print(f"\nWorkspace: {result['workspace']}")
        print(f"Run 'git log --oneline' in the workspace to see the commit history.")
