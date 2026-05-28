#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = ["ftl-reasons"]
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

import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from .agent import (
    get_artifacts_dir,
    get_repo_root,
    get_sdlc_dir,
    get_target_branch,
    log,
    log_separator,
    run_agent,
    set_context_dirs,
    set_repo_root,
    set_target_branch,
)

# Queue file handling for continuous mode
DEFAULT_QUEUE_PATH = Path("queue.txt")

# Effort level configurations
EFFORT_CONFIGS = {
    "minimal": {
        "description": "Fast execution (~5-15 min) - working solution with basic tests",
        "agents": ["planner", "implementer", "tester"],
        "max_iterations": 1,
        "skip_review": True,
        "skip_user": True,
        "max_inner_iterations": 1,  # No feedback loops
        "prompts": {
            "planner": "\n\nIMPORTANT - EFFORT LEVEL: MINIMAL\nKeep plan VERY brief (2-3 paragraphs max). Focus only on algorithm choice. Skip architectural discussions and detailed analysis.",
            "implementer": "\n\nIMPORTANT - EFFORT LEVEL: MINIMAL\nCreate a minimal working solution:\n- Basic function with minimal docstring (1-2 lines + Args/Returns)\n- Type hints optional\n- No input validation beyond what's strictly necessary\n- ONE solution file only (no README, no verify.py, no extra files)\n- Keep it simple and working",
            "tester": "\n\nIMPORTANT - EFFORT LEVEL: MINIMAL\nCreate 5-10 test cases maximum covering:\n- Examples from problem\n- Basic edge cases only\n- Skip usage guide, skip documentation\n- Just verify tests pass and you're done",
        },
    },
    "moderate": {
        "description": "Balanced approach (~30-60 min) - solid code with good practices",
        "agents": ["planner", "implementer", "reviewer", "tester"],
        "max_iterations": 1,
        "skip_user": True,
        "max_inner_iterations": 2,  # Limited feedback
        "prompts": {
            "planner": "\n\nEFFORT LEVEL: MODERATE\nKeep plan focused and concise. Cover key design decisions but avoid over-analysis.",
            "implementer": "\n\nEFFORT LEVEL: MODERATE\nCreate a clean solution:\n- Good docstring with examples\n- Type hints required\n- Basic input validation\n- One main solution file\n- Keep it professional but not over-engineered",
            "reviewer": "\n\nEFFORT LEVEL: MODERATE\nFocus on correctness and obvious bugs. Max 1-2 rounds of fixes. Be pragmatic.",
            "tester": "\n\nEFFORT LEVEL: MODERATE\nCreate 10-20 test cases with brief usage guide. Cover main scenarios and edge cases.",
        },
    },
    "maximum": {
        "description": "Production quality (~2-3 hours) - comprehensive testing and documentation",
        "agents": ["planner", "implementer", "reviewer", "tester", "user"],
        "max_iterations": 2,
        "skip_review": False,
        "skip_user": False,
        "max_inner_iterations": 3,  # Full feedback loops
        "prompts": {},  # No special instructions - full thoroughness
    },
}

# =============================================================================
# GitLab Integration
# =============================================================================


def check_glab_installed() -> bool:
    """Check if glab CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["glab", "auth", "status"], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def gitlab_get_username() -> str | None:
    """Get current GitLab username from glab auth status."""
    try:
        result = subprocess.run(
            ["glab", "auth", "status"], capture_output=True, text=True
        )
        # Parse output like "Logged in to gitlab.com as username"
        for line in result.stdout.split("\n") + result.stderr.split("\n"):
            if " as " in line:
                # Extract username after "as "
                parts = line.split(" as ")
                if len(parts) >= 2:
                    username = parts[-1].strip().split()[0]
                    # Remove any trailing punctuation
                    return username.rstrip(".,")
        return None
    except Exception:
        return None


def gitlab_fetch_issue(issue_number: int, cwd: Path | None = None) -> dict | None:
    """Fetch GitLab issue details via glab.

    Args:
        issue_number: The GitLab issue number
        cwd: Directory to run glab from (must be a git repo with GitLab remote)

    Returns dict with 'title', 'description', 'labels', 'web_url' or None on error.
    """
    try:
        result = subprocess.run(
            ["glab", "issue", "view", str(issue_number), "--output", "json"],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
        if result.returncode != 0:
            print(f"Error fetching issue #{issue_number}: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        return {
            "number": issue_number,
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "labels": data.get("labels", []),
            "web_url": data.get("web_url", ""),
        }
    except json.JSONDecodeError as e:
        print(f"Error parsing issue JSON: {e}")
        return None
    except Exception as e:
        print(f"Error fetching issue: {e}")
        return None


def gitlab_assign_issue(
    issue_number: int, username: str | None = None, cwd: Path | None = None
) -> bool:
    """Assign GitLab issue to a user (default: current user).

    Args:
        issue_number: The GitLab issue number
        username: GitLab username (default: current authenticated user)
        cwd: Directory to run glab from (must be a git repo with GitLab remote)
    """
    if username is None:
        username = gitlab_get_username()
    if username is None:
        print("Could not determine GitLab username")
        return False

    result = subprocess.run(
        ["glab", "issue", "update", str(issue_number), "--assignee", username],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        print(f"Warning: Could not assign issue #{issue_number}: {result.stderr}")
        return False
    print(f"Assigned issue #{issue_number} to {username}")
    return True


def gitlab_find_mr_template(workspace: Path) -> Path | None:
    """Find MR template in workspace.

    Checks standard GitLab template locations:
    - .gitlab/merge_request_templates/Default.md
    - .gitlab/merge_request_templates/default.md
    """
    template_paths = [
        workspace / ".gitlab" / "merge_request_templates" / "Default.md",
        workspace / ".gitlab" / "merge_request_templates" / "default.md",
    ]
    for path in template_paths:
        if path.exists():
            return path
    return None


def check_gh_installed() -> bool:
    """Check if gh CLI is installed and authenticated."""
    try:
        result = subprocess.run(
            ["gh", "auth", "status"], capture_output=True, text=True
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def github_fetch_issue(
    issue_number: int, repo: str | None = None, cwd: Path | None = None
) -> dict | None:
    """Fetch GitHub issue details via gh.

    Args:
        issue_number: The GitHub issue number
        repo: Repository slug (owner/repo). If None, auto-detected from cwd.
        cwd: Directory to run gh from (must be a git repo with GitHub remote)

    Returns dict with 'number', 'title', 'body', 'labels', 'url' or None on error.
    """
    try:
        cmd = [
            "gh",
            "issue",
            "view",
            str(issue_number),
            "--json",
            "number,title,body,labels,url,comments",
        ]
        if repo:
            cmd.extend(["--repo", repo])
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        if result.returncode != 0:
            print(f"Error fetching issue #{issue_number}: {result.stderr}")
            return None

        data = json.loads(result.stdout)
        comments = []
        for c in data.get("comments", []):
            author = c.get("author", {}).get("login", "unknown")
            body = c.get("body", "")
            if body:
                comments.append(f"**{author}:** {body}")
        return {
            "number": data.get("number", issue_number),
            "title": data.get("title", ""),
            "body": data.get("body", ""),
            "labels": [l.get("name", "") for l in data.get("labels", [])],
            "url": data.get("url", ""),
            "comments": comments,
        }
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error fetching GitHub issue #{issue_number}: {e}")
        return None


def github_branch_name(issue: dict) -> str:
    """Generate branch name from GitHub issue."""
    number = issue["number"]
    title_slug = slugify(issue["title"], max_length=40)
    return f"fix/issue-{number}-{title_slug}"


def github_build_prompt(issue: dict) -> str:
    """Build task prompt from GitHub issue."""
    prompt = f"## {issue['title']}\n\n"
    prompt += issue.get("body") or "(No description provided)"
    comments = issue.get("comments", [])
    if comments:
        prompt += "\n\n## Discussion\n\n"
        prompt += "\n\n".join(comments)
    prompt += f"\n\nCloses #{issue['number']}"
    return prompt


def github_fill_pr_template(
    task: str, github_issue: dict | None, workspace: Path
) -> str:
    """Generate PR description using Claude with context from the workspace."""
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    context_parts = []

    target = get_target_branch()
    diff_result = subprocess.run(
        ["git", "diff", f"origin/{target}..HEAD", "--", "src/", "tests/"],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    if diff_result.returncode == 0 and diff_result.stdout.strip():
        diff_content = diff_result.stdout[:8000]
        if len(diff_result.stdout) > 8000:
            diff_content += "\n... (diff truncated)"
        context_parts.append(f"## Git Diff\n```diff\n{diff_content}\n```")

    artifacts = get_artifacts_dir()
    plan_path = artifacts / "PLAN.md"
    if plan_path.exists():
        plan_content = plan_path.read_text()[:3000]
        context_parts.append(f"## PLAN.md\n{plan_content}")

    review_path = artifacts / "REVIEW.md"
    if review_path.exists():
        review_content = review_path.read_text()[:2000]
        context_parts.append(f"## REVIEW.md\n{review_content}")

    context = "\n\n---\n\n".join(context_parts)

    issue_info = ""
    if github_issue:
        issue_info = f"\nThis addresses GitHub issue #{github_issue['number']}: {github_issue['title']}"
        issue_info += f"\nInclude 'Closes #{github_issue['number']}' in the summary."

    prompt = f"""Write a concise GitHub pull request description.

## Original Task
{task}
{issue_info}

## Context
{context}

---

Instructions:
1. Write a clear Summary section (2-3 sentences)
2. Add a Changes section with bullet points of what changed
3. Add a Test Plan section
4. If this closes an issue, include "Closes #N"
5. Add "🤖 Generated with [ftl-sdlc-loop](https://github.com/benthomasson/ftl-sdlc-loop)" at the end

Output ONLY the PR description, nothing else."""

    print("  Using Claude to generate PR description...")
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0 or not result.stdout.strip():
        print("  Warning: Claude failed to generate description, using fallback")
        fallback = f"## Summary\n\n{task[:500]}\n\n"
        if github_issue:
            fallback += f"Closes #{github_issue['number']}\n\n"
        fallback += "🤖 Generated with [ftl-sdlc-loop](https://github.com/benthomasson/ftl-sdlc-loop)"
        return fallback

    return result.stdout.strip()


def gitlab_fill_mr_template(
    template_content: str, task: str, gitlab_issue: dict | None, workspace: Path
) -> str:
    """Fill in MR template using Claude to generate intelligent content.

    Passes the template to Claude along with context (PLAN.md, git diff, etc.)
    and asks Claude to fill it out properly.
    """
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    # Gather context for Claude
    context_parts = []

    # Git diff for actual changes (compare against origin's target branch)
    target = get_target_branch()
    diff_result = subprocess.run(
        ["git", "diff", f"origin/{target}..HEAD", "--", "src/", "tests/"],
        cwd=workspace,
        env=env,
        capture_output=True,
        text=True,
    )
    if diff_result.returncode == 0 and diff_result.stdout.strip():
        # Limit diff size
        diff_content = diff_result.stdout[:8000]
        if len(diff_result.stdout) > 8000:
            diff_content += "\n... (diff truncated)"
        context_parts.append(f"## Git Diff\n```diff\n{diff_content}\n```")

    # PLAN.md (from artifacts)
    artifacts = get_artifacts_dir()
    plan_path = artifacts / "PLAN.md"
    if plan_path.exists():
        plan_content = plan_path.read_text()[:3000]
        context_parts.append(f"## PLAN.md\n{plan_content}")

    # REVIEW.md (from artifacts)
    review_path = artifacts / "REVIEW.md"
    if review_path.exists():
        review_content = review_path.read_text()[:2000]
        context_parts.append(f"## REVIEW.md\n{review_content}")

    # Test results if available (from artifacts)
    test_path = artifacts / "tester" / "USAGE.md"
    if test_path.exists():
        test_content = test_path.read_text()[:1500]
        context_parts.append(f"## Test Results\n{test_content}")

    context = "\n\n---\n\n".join(context_parts)

    # Build prompt for Claude
    issue_info = ""
    if gitlab_issue:
        issue_info = f"\nThis addresses GitLab issue #{gitlab_issue['number']}: {gitlab_issue['title']}"
        issue_info += f"\nInclude 'Closes #{gitlab_issue['number']}' in the Related Issues section."

    prompt = f"""Fill out this GitLab merge request template based on the context provided.

## Original Task
{task}
{issue_info}

## Context
{context}

## MR Template to Fill Out
{template_content}

---

Instructions:
1. Fill in each section of the template with appropriate content based on the context
2. For "Type of Change" checkboxes, mark the appropriate one with [x]
3. Be concise but informative - this is for code reviewers
4. Keep the original template structure and headings
5. Add "🤖 Generated with [ftl-sdlc-loop](https://github.com/benthomasson/ftl-sdlc-loop)" at the end

Output ONLY the filled-in template, nothing else."""

    # Run Claude to fill the template
    print("  Using Claude to fill MR template...")
    result = subprocess.run(
        ["claude", "-p", prompt, "--output-format", "text"],
        capture_output=True,
        text=True,
        env=env,
    )

    if result.returncode != 0 or not result.stdout.strip():
        print("  Warning: Claude failed to fill template, using fallback")
        # Fallback to simple description
        fallback = f"## Description\n\n{task[:500]}\n\n"
        if gitlab_issue:
            fallback += f"Closes #{gitlab_issue['number']}\n\n"
        fallback += "🤖 Generated with [ftl-sdlc-loop](https://github.com/benthomasson/ftl-sdlc-loop)"
        return fallback

    return result.stdout.strip()


def gitlab_create_mr(
    source_branch: str,
    title: str,
    description: str,
    target_branch: str = "main",
    assignee: str | None = None,
    cwd: Path | None = None,
) -> str | None:
    """Create GitLab merge request via glab.

    Args:
        source_branch: Branch with changes
        title: MR title
        description: MR description/body
        target_branch: Branch to merge into (default: main)
        assignee: GitLab username to assign
        cwd: Directory to run glab from (must be a git repo with GitLab remote)

    Returns MR URL on success, None on failure.
    """
    cmd = [
        "glab",
        "mr",
        "create",
        "--source-branch",
        source_branch,
        "--target-branch",
        target_branch,
        "--title",
        title,
        "--description",
        description,
        "--fill",  # Fill in defaults
    ]

    if assignee:
        cmd.extend(["--assignee", assignee])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)

    if result.returncode != 0:
        print(f"Error creating MR: {result.stderr}")
        return None

    # Parse MR URL from output
    output = result.stdout + result.stderr
    for line in output.split("\n"):
        if "merge_requests" in line or "http" in line.lower():
            # Extract URL
            import re

            urls = re.findall(r"https?://[^\s]+", line)
            if urls:
                return urls[0]

    print(f"MR created: {output.strip()}")
    return output.strip()


def slugify(text: str, max_length: int = 50) -> str:
    """Convert text to URL-friendly slug."""
    import re

    # Lowercase and replace spaces/special chars with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower())
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Truncate
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    return slug


def gitlab_branch_name(issue: dict) -> str:
    """Generate branch name from GitLab issue."""
    number = issue["number"]
    title_slug = slugify(issue["title"], max_length=40)
    return f"fix/issue-{number}-{title_slug}"


def gitlab_build_prompt(issue: dict) -> str:
    """Build task prompt from GitLab issue."""
    prompt = f"## {issue['title']}\n\n"
    prompt += issue["description"] or "(No description provided)"
    prompt += f"\n\nCloses #{issue['number']}"
    return prompt


def read_queue(queue_path: Path) -> list[str]:
    """Read all tasks from the queue file. Returns empty list if file doesn't exist."""
    if not queue_path.exists():
        return []
    content = queue_path.read_text().strip()
    if not content:
        return []
    return [line.strip() for line in content.split("\n") if line.strip()]


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
        queue_path.write_text("\n".join(remaining) + "\n")
    else:
        queue_path.write_text("")

    return task


def git_commit(message: str, files: list[str] | None = None) -> bool:
    """Commit source-code changes to git, excluding .sdlc-loop/.

    Since SDLC artifacts live under .sdlc-loop/ (which is gitignored),
    this only commits real source changes.  If there are no staged
    changes after exclusion, it returns False.
    """
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    repo = get_repo_root()

    try:
        # Stage files
        if files:
            for f in files:
                subprocess.run(
                    ["git", "add", f],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )
        else:
            subprocess.run(
                ["git", "add", "-A", "--", ".", ":!.sdlc-loop/"],
                cwd=repo,
                env=env,
                capture_output=True,
            )

        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=repo,
            env=env,
            capture_output=True,
        )
        if result.returncode == 0:
            # No changes staged
            return False

        # Commit
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo,
            env=env,
            capture_output=True,
        )
        return True
    except Exception as e:
        print(f"  [git commit failed: {e}]")
        return False


def load_env_file(env_path: str) -> bool:
    """Load environment variables from a .env file.

    Reads the file and loads its variables into os.environ so agents
    inherit them.  If the file is inside the repo, ensures .env is in
    .gitignore.

    Returns True if successful, False otherwise.
    """
    source = Path(env_path).expanduser().resolve()
    if not source.exists():
        print(f"Error: .env file not found: {source}")
        return False

    print(f"Loading .env from {source}")

    # Ensure .env is in .gitignore
    repo = get_repo_root()
    gitignore = repo / ".gitignore"
    gitignore_content = gitignore.read_text() if gitignore.exists() else ""
    if ".env" not in gitignore_content:
        with open(gitignore, "a") as f:
            if gitignore_content and not gitignore_content.endswith("\n"):
                f.write("\n")
            f.write(".env\n")
        print("Added .env to .gitignore")

    # Parse and load the .env file
    loaded_vars = []
    with open(source) as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue
            # Handle KEY=VALUE format
            if "=" in line:
                # Handle optional 'export ' prefix
                if line.startswith("export "):
                    line = line[7:]
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()
                # Remove quotes if present
                if (value.startswith('"') and value.endswith('"')) or (
                    value.startswith("'") and value.endswith("'")
                ):
                    value = value[1:-1]
                os.environ[key] = value
                loaded_vars.append(key)

    print(f"Loaded {len(loaded_vars)} environment variables: {', '.join(loaded_vars)}")
    return True


def init_sdlc_dir():
    """Initialize the .sdlc-loop/ directory structure in the code repo.

    Creates:
      .sdlc-loop/agents/      - per-agent session directories
      .sdlc-loop/artifacts/    - SDLC documents (plans, reviews, etc.)
      .sdlc-loop/entries/      - iteration-ordered entries
      .sdlc-loop/logs/         - log files
      .sdlc-loop/pids/         - agent PID files

    Also ensures .sdlc-loop/ is listed in the repo's .gitignore.
    """
    sdlc = get_sdlc_dir()
    for subdir in ["agents", "artifacts", "entries", "logs", "pids"]:
        (sdlc / subdir).mkdir(parents=True, exist_ok=True)

    # Ensure .sdlc-loop/ is gitignored
    repo = get_repo_root()
    gitignore = repo / ".gitignore"
    gitignore_content = gitignore.read_text() if gitignore.exists() else ""
    if ".sdlc-loop/" not in gitignore_content:
        with open(gitignore, "a") as f:
            if gitignore_content and not gitignore_content.endswith("\n"):
                f.write("\n")
            f.write(".sdlc-loop/\n")
        print("Added .sdlc-loop/ to .gitignore")


def push_workspace(
    branch: str = "main", create_pr: bool = False, squash: bool = True
) -> bool:
    """Push repo changes to the remote.

    Squashes commits and pushes.  SDLC artifacts are already gitignored
    so no cleanup is needed.  Optionally creates a pull request instead
    of pushing directly.

    Returns True if successful, False otherwise.
    """
    repo = get_repo_root()
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)

    if not repo.exists() or not (repo / ".git").exists():
        print(f"Error: {repo} is not a git repository")
        return False

    # Read task description from artifacts
    task_file = get_artifacts_dir() / "TASK.md"
    if task_file.exists():
        lines = task_file.read_text().strip().splitlines()
        desc_lines = [
            l
            for l in lines
            if l and not l.startswith("# ") and not l.startswith("Started:")
        ]
        task_desc = "\n".join(desc_lines)[:200] or "ftl-sdlc-loop changes"
    else:
        task_desc = "ftl-sdlc-loop changes"

    # Get current branch
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    current_branch = result.stdout.strip()

    # Find the original commit before ftl-sdlc-loop started
    result = subprocess.run(
        ["git", "log", "--oneline", f"origin/{branch}..HEAD"],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )
    commit_count = len([l for l in result.stdout.strip().split("\n") if l])

    if squash and commit_count > 1:
        print(f"Squashing {commit_count} commits...")
        subprocess.run(
            ["git", "reset", "--soft", f"origin/{branch}"],
            cwd=repo,
            env=env,
            capture_output=True,
        )
        subprocess.run(
            [
                "git",
                "commit",
                "-m",
                f"{task_desc}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
            ],
            cwd=repo,
            env=env,
            capture_output=True,
        )

    # Check if there are actual changes
    diff_check = subprocess.run(
        ["git", "diff", "--stat", f"origin/{branch}..HEAD"],
        cwd=repo, env=env, capture_output=True, text=True
    )
    if not diff_check.stdout.strip():
        print("No code changes to push.")
        return False

    if create_pr:
        print(f"Pushing {current_branch} branch...")
        result = subprocess.run(
            ["git", "push", "-u", "origin", current_branch],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error pushing: {result.stderr}")
            return False

        print("Creating pull request...")
        result = subprocess.run(
            ["gh", "pr", "create", "--fill", "--base", branch],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error creating PR: {result.stderr}")
            print("You can create the PR manually or push directly with --push")
            return False

        print(f"Pull request created: {result.stdout.strip()}")
        return True
    else:
        print(f"Merging {current_branch} into {branch}...")
        subprocess.run(
            ["git", "checkout", branch], cwd=repo, env=env, capture_output=True
        )
        result = subprocess.run(
            ["git", "merge", current_branch, "--no-edit"],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error merging: {result.stderr}")
            return False

        print(f"Pushing to origin/{branch}...")
        result = subprocess.run(
            ["git", "push", "origin", branch],
            cwd=repo,
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"Error pushing: {result.stderr}")
            return False

        print(f"Successfully pushed to origin/{branch}")
        return True


def save_artifact(name: str, content: str) -> Path:
    """Save an artifact to .sdlc-loop/artifacts/."""
    path = get_artifacts_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def save_source_file(name: str, content: str) -> Path:
    """Save extracted source code to the repo root (not artifacts)."""
    path = get_repo_root() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


def parse_verdict(response: str) -> dict:
    """Parse a structured verdict block from agent output.

    Expects a block like:
        ## Verdict
        STATUS: APPROVED
        OPEN_ISSUES: none

    or:
        ## Verdict
        STATUS: NEEDS_CHANGES
        OPEN_ISSUES:
        - issue 1
        - issue 2

    Falls back to legacy string matching if the structured block isn't found.
    """
    import re

    result = {"status": None, "open_issues": []}

    # Try structured format first
    # Terminators: blank line, next heading, or end-of-string
    verdict_match = re.search(
        r"## Verdict\s*\n"
        r"STATUS:\s*(\S+)\s*\n"
        r"(?:OPEN_ISSUES:\s*(.*?))?(?=\n\n|\n## |\Z)",
        response,
        re.DOTALL,
    )

    if verdict_match:
        result["status"] = verdict_match.group(1).strip()
        issues_text = verdict_match.group(2)
        if issues_text:
            issues_text = issues_text.strip()
            if issues_text.lower() != "none" and issues_text:
                # Only accept lines starting with "- " as issues
                result["open_issues"] = [
                    line.strip().lstrip("- ").strip()
                    for line in issues_text.split("\n")
                    if line.strip().startswith("-")
                ]
        return result

    # Legacy fallback — scan for keywords
    if "APPROVED" in response and "NEEDS_CHANGES" not in response:
        result["status"] = "APPROVED"
    elif "NEEDS_CHANGES" in response:
        result["status"] = "NEEDS_CHANGES"
    elif "TESTS_PASSED" in response and "TESTS_FAILED" not in response:
        result["status"] = "TESTS_PASSED"
    elif "TESTS_FAILED" in response:
        result["status"] = "TESTS_FAILED"
    elif "SATISFIED" in response and "NEEDS_IMPROVEMENT" not in response:
        result["status"] = "SATISFIED"
    elif "NEEDS_IMPROVEMENT" in response:
        result["status"] = "NEEDS_IMPROVEMENT"

    return result


def apply_exit_gate(verdict: dict, agent_type: str) -> dict:
    """Check for contradictions: positive status + open issues.

    For reviewer/tester: overrides to negative status.
    For user: sets escalate flag for human review.
    """
    if not verdict.get("open_issues"):
        return verdict

    status = verdict.get("status", "")

    positive_to_negative = {
        "reviewer": ("APPROVED", "NEEDS_CHANGES"),
        "tester": ("TESTS_PASSED", "TESTS_FAILED"),
        "user": ("SATISFIED", "NEEDS_IMPROVEMENT"),
    }

    if agent_type in positive_to_negative:
        positive, negative = positive_to_negative[agent_type]
        if status == positive:
            if agent_type in ("reviewer", "tester"):
                print(
                    f"  [EXIT GATE] {agent_type} declared {positive} but listed open issues — overriding to {negative}"
                )
                verdict["status"] = negative
            elif agent_type == "user":
                print(
                    "  [EXIT GATE] User declared SATISFIED but listed open issues — escalating to human"
                )
                verdict["escalate"] = True

    return verdict


def save_entry(
    iteration: int, role: str, content: str, inner: int | None = None
) -> Path:
    """Save agent output to iteration-ordered entry structure.

    Args:
        iteration: Outer iteration number
        role: Agent role name
        content: Content to save
        inner: Inner loop iteration (for reviewer/implementer cycles)
    """
    entry_dir = get_sdlc_dir() / "entries" / f"iteration-{iteration}"
    entry_dir.mkdir(parents=True, exist_ok=True)
    if inner is not None:
        path = entry_dir / f"{role}_{inner}.md"
    else:
        path = entry_dir / f"{role}.md"
    path.write_text(content)
    return path


from .reasons import (
    get_reasons_db,
    reasons_add,
    reasons_check_stale,
    reasons_compact,
    reasons_init,
    reasons_list_gated,
    reasons_list_warnings,
    set_reasons_db,
)


def planner(
    task: str,
    user_feedback: str | None = None,
    shared_understanding: str | None = None,
    iteration: int = 1,
    continue_conversations: bool = False,
) -> dict:
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

### Output Guidelines

- **Use table format for file changes.** For each implementation step, include a table with columns: File, Line(s), Change Description. This lets the implementer go straight to the code.
- **Include line numbers for every change site.** Read the actual files and reference specific line numbers. Do not give vague locations.
- **Make decisions — do not defer to the implementer.** If a choice exists (e.g., "consider enriching X"), decide yes or no and state your reasoning. The implementer handles HOW, not WHAT.
- **Analyze both directions for matching/lookup changes.** If a change involves matching A against B, explicitly verify that B-to-A also works correctly. State your analysis.
- **Complete all plan steps.** Never truncate or abbreviate. If the plan is long, that is fine — an incomplete plan is worse than a long one.

1. Requirements analysis - what exactly needs to be built and why
2. Implementation steps (suggestions for the implementer, using table format above)
3. Key design decisions
4. Success criteria - what the user should be able to do when complete
5. If addressing user feedback, explain what you're prioritizing and why

## SELF-REVIEW

After writing your plan, reflect:
1. What went well in your planning process?
2. What information were you missing that would have helped?
3. What would make your job easier next time?

Be concise and actionable. The implementer may push back on the HOW.

If you need clarification or are stuck, you can escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent(
        "planner", prompt, continue_session=(continue_conversations or iteration > 1)
    )

    # Save plan to artifacts (versioned by iteration)
    save_artifact(
        f"PLAN_{iteration}.md",
        f"# Plan (Iteration {iteration})\n\nTask: {task}\n\n{response}",
    )

    return {
        "output": response,
    }


def implementer(
    plan: str,
    task: str,
    reviewer_feedback: str | None = None,
    iteration: int = 1,
    continue_conversations: bool = False,
) -> dict:
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

    # Phase 1: Make the actual changes — no prose, just tool calls
    repo = get_repo_root()
    implement_prompt = f"""You are a software implementer. Your ONLY job right now is to
make code changes using the Edit and Write tools. Do NOT write prose or
documentation. Do NOT create markdown files. Just find the files and edit them.

You are running in the SOURCE TREE of the project at: {repo}
IMPORTANT: Only modify files inside {repo}. Do NOT modify files outside this directory.

Steps:
1. Use Glob/Grep to find the files mentioned in the plan
2. Use Read to examine each file
3. Use Edit to modify existing files (provide exact old_string and new_string)
4. Use Write to create new files (e.g. new test files)
5. Use Read to verify your changes are correct

Do NOT write any markdown files. Do NOT create IMPLEMENTATION.md or notes.
Your ONLY output should be a brief list of files you changed.

ORIGINAL TASK: {task}

PLANNER'S PLAN:
{plan}
{feedback_section}
If you need clarification or are stuck, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    run_agent(
        "implementer",
        implement_prompt,
        continue_session=(continue_conversations or iteration > 1),
        auto_commit=False,
    )

    # Phase 2: Describe what was done (continue session so it has context)
    describe_prompt = """Now describe what you just did. List the files you modified and
what changes you made in each one. Include a self-review:
1. Which source files did you actually modify? (list file paths)
2. What went well?
3. What was unclear in the plan?
4. Any concerns for the reviewer?"""

    response = run_agent("implementer", describe_prompt, continue_session=True, auto_commit=False)

    # Extract and save code blocks
    # Supports multiple formats:
    #   ```python filename.py
    #   **File: `filename.py`** followed by ```python
    #   # filename.py at start of code block
    import re

    files_created = []

    # Pattern 1: ```python filename.py\ncode```
    pattern1 = re.findall(
        r"```(\w+)?\s+(\S+\.(?:py|js|ts|sh|yaml|yml|json))\n(.*?)```",
        response,
        re.DOTALL,
    )
    for lang, filename, code in pattern1:
        save_source_file(filename.strip(), code.strip())
        files_created.append(filename.strip())

    # Pattern 2: **File: `filename.py`** followed by ```\ncode```
    pattern2 = re.findall(
        r"\*\*File:\s*`(\S+\.(?:py|js|ts|sh|yaml|yml|json))`\*\*\s*\n+```\w*\n(.*?)```",
        response,
        re.DOTALL,
    )
    for filename, code in pattern2:
        if filename not in files_created:
            save_source_file(filename.strip(), code.strip())
            files_created.append(filename.strip())

    # Pattern 3: # filename.py as first line in code block
    pattern3 = re.findall(
        r"```\w*\n#\s*(\S+\.(?:py|js|ts|sh|yaml|yml|json))\n(.*?)```",
        response,
        re.DOTALL,
    )
    for filename, code in pattern3:
        if filename not in files_created:
            save_source_file(filename.strip(), code.strip())
            files_created.append(filename.strip())

    # files_created is already populated above
    # Note: versioned artifact save happens in run_iteration()

    if files_created:
        git_commit(f"[implementer] Implement: {', '.join(files_created)}")
    else:
        git_commit("[implementer] Implementation notes")

    return {"output": response, "files_created": files_created}


def reviewer(
    code: str, task: str, iteration: int = 1, continue_conversations: bool = False
) -> dict:
    """
    Reviewer: Provides feedback to implementer AND feed-forward to tester.
    Returns structured feedback for both.
    Includes self-review.
    """
    prompt = f"""You are a code reviewer. Review this implementation and provide
feedback for two audiences.

Your primary job is to FIND ERRORS, not to encourage. If the code has problems,
say NEEDS_CHANGES. Do not approve code with known issues just because the overall
structure is acceptable. A single serious bug is grounds for NEEDS_CHANGES.

ORIGINAL TASK: {task}

CODE:
{code}

Provide your response in FOUR parts:

## FEEDBACK FOR IMPLEMENTER

- Correctness: Does it fulfill the task?
- Error handling: Are errors clear and actionable?
- Usability: Can users easily understand failures?
- If changes are needed, list specific changes required

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

## Verdict

At the END of your response, provide this block EXACTLY:

STATUS: APPROVED
OPEN_ISSUES: none

or:

STATUS: NEEDS_CHANGES
OPEN_ISSUES:
- specific issue 1
- specific issue 2

If you need clarification or are blocked, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent(
        "reviewer", prompt, continue_session=(continue_conversations or iteration > 1)
    )

    verdict = parse_verdict(response)
    verdict = apply_exit_gate(verdict, "reviewer")

    return {
        "output": response,
        "approved": verdict["status"] == "APPROVED",
        "verdict": verdict,
    }


def tester(
    code: str,
    task: str,
    reviewer_notes: str,
    iteration: int = 1,
    continue_conversations: bool = False,
) -> dict:
    """
    Tester: Documents how to use the software.
    Provides usage instructions to the User agent.
    Includes self-review.
    """
    repo = get_repo_root()
    prompt = f"""You are a QA tester. Your job is to:
1. Create tests for this implementation
2. Document HOW TO USE the software for the User

You are running in the SOURCE TREE of the project at: {repo}
IMPORTANT: Only modify files inside {repo}. Do NOT modify files outside this directory.

Test files should be created alongside the existing test infrastructure — use Glob to find
where existing tests live (e.g. `**/tests/**/test_*.py`) and put new
tests in the appropriate location, NOT in a separate `tester/` directory.

You have access to Write, Edit, Read, Glob, Grep, and Bash tools.
USE THE WRITE TOOL to create test files in the project's test directories.
USE BASH to run the tests and verify they pass.

ORIGINAL TASK: {task}

CODE:
{code}

REVIEWER'S NOTES FOR TESTING:
{reviewer_notes}

Provide your response in FOUR parts:

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

## Verdict

At the END of your response, provide this block EXACTLY:

STATUS: TESTS_PASSED
OPEN_ISSUES: none

or:

STATUS: TESTS_FAILED
OPEN_ISSUES:
- specific failure 1
- specific failure 2

If TESTS_FAILED, clearly describe what needs to be fixed so the implementer can address it.

If you need clarification or are blocked, escalate to a human:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent(
        "tester", prompt, continue_session=(continue_conversations or iteration > 1),
        auto_commit=False,
    )

    # Extract and save test files
    import re

    # Extract test files - support multiple formats
    test_files = []

    # Pattern 1: ```python test_*.py
    pattern1 = re.findall(
        r"```(?:python)?\s*(test_\S+\.py)\n(.*?)```", response, re.DOTALL
    )
    for filename, code in pattern1:
        save_source_file(filename.strip(), code.strip())
        test_files.append(filename.strip())

    # Pattern 2: **File: `test_*.py`** followed by code block
    pattern2 = re.findall(
        r"\*\*File:\s*`(test_\S+\.py)`\*\*\s*\n+```\w*\n(.*?)```", response, re.DOTALL
    )
    for filename, code in pattern2:
        if filename.strip() not in test_files:
            save_source_file(filename.strip(), code.strip())
            test_files.append(filename.strip())

    if test_files:
        git_commit(f"[tester] Tests: {', '.join(test_files)}")
    else:
        git_commit("[tester] Tests and usage documentation")

    # Determine if tests passed
    verdict = parse_verdict(response)
    verdict = apply_exit_gate(verdict, "tester")
    tests_passed = verdict["status"] == "TESTS_PASSED"

    return {
        "output": response,
        "test_files": test_files,
        "tests_passed": tests_passed,
        "verdict": verdict,
    }


def user(
    code: str,
    task: str,
    usage_instructions: str,
    iteration: int = 1,
    continue_conversations: bool = False,
) -> dict:
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

## Verdict

At the END of your response, provide this block EXACTLY:

STATUS: SATISFIED
OPEN_ISSUES: none

or:

STATUS: NEEDS_IMPROVEMENT
OPEN_ISSUES:
- specific issue 1
- specific issue 2

The planner will review your feature requests and decide which to implement.

If you are stuck or need help from a human, escalate:
QUESTION FOR HUMAN: [your question here]"""

    response = run_agent(
        "user", prompt, continue_session=(continue_conversations or iteration > 1)
    )

    # Save user feedback (versioned by iteration)
    save_artifact(
        f"USER_FEEDBACK_{iteration}.md",
        f"# User Feedback (Iteration {iteration})\n\n{response}",
    )

    verdict = parse_verdict(response)
    verdict = apply_exit_gate(verdict, "user")

    return {
        "output": response,
        "satisfied": verdict["status"] == "SATISFIED",
        "verdict": verdict,
    }


def process_agent_output(
    agent_name: str, output: str, iteration: int, no_questions: bool = False
) -> str:
    """Process agent output, checking for escalations."""
    escalation = check_for_escalation(output)
    if escalation:
        human_response = request_human_input(
            agent_name, escalation, iteration, no_questions
        )
        output += f"\n\n## Human Response\n\n{human_response}"

    return output


def run_iteration(
    task: str,
    iteration: int,
    user_feedback: str | None = None,
    shared_understanding: str | None = None,
    continue_conversations: bool = False,
    max_inner_iterations: int = 3,
    effort_config: dict | None = None,
    no_questions: bool = False,
    existing_plan: str | None = None,
) -> dict:
    """Run one iteration of the development loop.

    Inner loops:
    - Reviewer → Implementer (if NEEDS_CHANGES)
    - Tester → Implementer (if tests fail)

    If existing_plan is provided, skips the planner stage.
    """
    if effort_config is None:
        effort_config = EFFORT_CONFIGS["moderate"]

    results = {}
    results["unresolved_issues"] = []
    skip_review = effort_config.get("skip_review", False)
    skip_user = effort_config.get("skip_user", False)

    # Add effort-specific instructions to task
    task_with_effort = task + effort_config.get("prompts", {}).get("planner", "")

    # Stage 1: Planning (skip if existing plan provided)
    if existing_plan:
        print("\n[1/5] PLANNER skipped - using provided plan")
        results["planner"] = existing_plan
        plan_result = {"output": existing_plan}  # For beliefs registration below
        save_artifact(
            f"PLAN_{iteration}.md",
            f"# Plan (Provided, Iteration {iteration})\n\nTask: {task}\n\n{existing_plan}",
        )
        save_entry(iteration, "planner", results["planner"])
        print(f"\n{results['planner'][:500]}...\n")
    else:
        print("\n[1/5] PLANNER designing solution...")
        plan_result = planner(
            task_with_effort,
            user_feedback,
            shared_understanding,
            iteration,
            continue_conversations,
        )
        results["planner"] = process_agent_output(
            "planner", plan_result["output"], iteration, no_questions
        )
        save_entry(iteration, "planner", results["planner"])
        print(f"\n{results['planner']}\n")

    # Reasons: register planner decisions as AXIOMs
    if get_reasons_db().exists():
        import re

        numbered_items = re.findall(
            r"^\d+\.\s+(.+)$", plan_result.get("output", ""), re.MULTILINE
        )
        for i, item in enumerate(numbered_items[:5]):
            reasons_add(f"plan-{iteration}-{i+1}", item[:200], label="AXIOM")

    # Stage 2 & 3: Implementation + Review loop
    reviewer_feedback = None
    inner_iteration = 0

    while inner_iteration < max_inner_iterations:
        inner_iteration += 1

        # Implementation
        if inner_iteration == 1:
            print("\n[2/5] IMPLEMENTER writing code...")
        else:
            print(f"\n[2/5] IMPLEMENTER fixing issues (attempt {inner_iteration})...")

        # Add effort-specific instructions to task for implementer
        task_for_impl = task + effort_config.get("prompts", {}).get("implementer", "")
        impl_result = implementer(
            results["planner"],
            task_for_impl,
            reviewer_feedback,
            iteration,
            continue_conversations or inner_iteration > 1,
        )
        results["implementer"] = process_agent_output(
            "implementer", impl_result["output"], iteration, no_questions
        )
        results["files_created"] = impl_result.get("files_created", [])
        save_entry(
            iteration, "implementer", results["implementer"], inner=inner_iteration
        )
        save_artifact(
            f"IMPLEMENTATION_{iteration}_{inner_iteration}.md",
            f"# Implementation (Iteration {iteration}, Attempt {inner_iteration})\n\n{results['implementer']}",
        )
        print(f"\n{results['implementer']}\n")

        # Reasons: register implemented files as DERIVED claims
        if get_reasons_db().exists():
            for f in results["files_created"]:
                reasons_add(f"impl-{iteration}-{f}", f"Created {f}", label="DERIVED", source=f)

        # Review (skip if effort level is minimal)
        if skip_review:
            print("\n[3/5] REVIEWER skipped (effort level: minimal)")
            results["reviewer"] = "Skipped - minimal effort level"
            results["approved"] = True  # Auto-approve
            review_result = {
                "approved": True,
                "output": results["reviewer"],
                "verdict": {"status": "APPROVED", "open_issues": []},
            }
        else:
            print("\n[3/5] REVIEWER checking implementation...")
            task_for_reviewer = task + effort_config.get("prompts", {}).get(
                "reviewer", ""
            )
            review_result = reviewer(
                results["implementer"],
                task_for_reviewer,
                iteration,
                continue_conversations or inner_iteration > 1,
            )
            results["reviewer"] = process_agent_output(
                "reviewer", review_result["output"], iteration, no_questions
            )
            results["approved"] = review_result["approved"]
            save_entry(
                iteration, "reviewer", results["reviewer"], inner=inner_iteration
            )
            save_artifact(
                f"REVIEW_{iteration}_{inner_iteration}.md",
                f"# Review (Iteration {iteration}, Attempt {inner_iteration})\n\n{results['reviewer']}",
            )
            print(f"\n{results['reviewer']}\n")

        # Reasons: register reviewer issues as WARNINGs
        if get_reasons_db().exists():
            for i, issue in enumerate(
                review_result.get("verdict", {}).get("open_issues", [])
            ):
                reasons_add(
                    f"review-warn-{iteration}-{inner_iteration}-{i+1}",
                    issue[:200],
                    label="WARNING",
                )
            reasons_check_stale()

        if review_result["approved"]:
            print("  [Reviewer APPROVED - proceeding to tester]")
            break
        else:
            print("  [Reviewer requested CHANGES - looping back to implementer]")
            reviewer_feedback = results["reviewer"]

    # Track unresolved reviewer issues if inner loop exhausted without approval
    if not review_result["approved"]:
        unresolved = review_result.get("verdict", {}).get("open_issues", [])
        if unresolved:
            results["unresolved_issues"].extend(unresolved)
            print(
                f"  [WARNING] {len(unresolved)} reviewer issues unresolved after {max_inner_iterations} attempts"
            )

    # Stage 4: Testing (with potential loop back to implementer)
    tester_iteration = 0
    tester_feedback = None

    while tester_iteration < max_inner_iterations:
        tester_iteration += 1

        if tester_iteration == 1:
            print("\n[4/5] TESTER creating tests and usage docs...")
        else:
            # Re-run implementer with tester feedback
            print(
                f"\n[2/5] IMPLEMENTER fixing test failures (attempt {tester_iteration})..."
            )
            impl_result = implementer(
                results["planner"], task, tester_feedback, iteration, True
            )
            results["implementer"] = process_agent_output(
                "implementer", impl_result["output"], iteration, no_questions
            )
            results["files_created"] = impl_result.get("files_created", [])
            # Use tester_iteration + max offset to distinguish from review loop iterations
            impl_attempt = inner_iteration + tester_iteration
            save_entry(
                iteration, "implementer", results["implementer"], inner=impl_attempt
            )
            save_artifact(
                f"IMPLEMENTATION_{iteration}_{impl_attempt}.md",
                f"# Implementation (Iteration {iteration}, Attempt {impl_attempt} - test fix)\n\n{results['implementer']}",
            )
            print(f"\n{results['implementer']}\n")

            print("\n[4/5] TESTER re-running tests...")

        # Inject unresolved issues into reviewer notes for the tester
        reviewer_notes_for_tester = results["reviewer"]
        if results["unresolved_issues"]:
            reviewer_notes_for_tester += (
                "\n\nWARNING — UNRESOLVED ISSUES FROM PREVIOUS STAGES:\n"
            )
            reviewer_notes_for_tester += "\n".join(
                f"- {issue}" for issue in results["unresolved_issues"]
            )

        # Add effort-specific instructions to task for tester
        task_for_tester = task + effort_config.get("prompts", {}).get("tester", "")
        test_result = tester(
            results["implementer"],
            task_for_tester,
            reviewer_notes_for_tester,
            iteration,
            continue_conversations or tester_iteration > 1,
        )
        results["tester"] = process_agent_output(
            "tester", test_result["output"], iteration, no_questions
        )
        results["tests_passed"] = test_result.get("tests_passed", True)
        save_entry(iteration, "tester", results["tester"], inner=tester_iteration)
        save_artifact(
            f"TESTER_{iteration}_{tester_iteration}.md",
            f"# Tester (Iteration {iteration}, Attempt {tester_iteration})\n\n{results['tester']}",
        )
        print(f"\n{results['tester']}\n")

        # Reasons: register test results as OBSERVATIONs
        if get_reasons_db().exists():
            status = test_result.get("verdict", {}).get("status", "UNKNOWN")
            reasons_add(
                f"test-{iteration}-{tester_iteration}", f"Tests {status}", label="OBSERVATION"
            )
            for i, issue in enumerate(
                test_result.get("verdict", {}).get("open_issues", [])
            ):
                reasons_add(
                    f"test-warn-{iteration}-{tester_iteration}-{i+1}",
                    issue[:200],
                    label="WARNING",
                )

        if results["tests_passed"]:
            print("  [Tests passed - proceeding to user]")
            break
        else:
            print("  [Tests failed - looping back to implementer]")
            tester_feedback = f"TESTER FEEDBACK (tests failed):\n{results['tester']}"

    # Track unresolved tester issues if inner loop exhausted without passing
    if not results["tests_passed"]:
        unresolved = test_result.get("verdict", {}).get("open_issues", [])
        if unresolved:
            results["unresolved_issues"].extend(unresolved)
            print(
                f"  [WARNING] {len(unresolved)} test issues unresolved after {max_inner_iterations} attempts"
            )

    # Stage 5: User feedback (skip if effort level is minimal or moderate)
    # Initialize reasons_warnings before the if/else to avoid UnboundLocalError
    reasons_warnings = None

    if skip_user:
        print("\n[5/5] USER skipped (effort level does not include user testing)")
        results["user"] = "Skipped - effort level does not include user testing"
        results["user_satisfied"] = True  # Auto-satisfy
        user_result = {
            "satisfied": True,
            "output": results["user"],
            "verdict": {"status": "SATISFIED", "open_issues": []},
        }
        save_entry(iteration, "user", results["user"])
    else:
        print("\n[5/5] USER trying the code...")

        # Inject unresolved issues and beliefs into user context
        usage_for_user = results["tester"]
        if results["unresolved_issues"]:
            usage_for_user += "\n\nWARNING — UNRESOLVED ISSUES FROM PREVIOUS STAGES:\n"
            usage_for_user += "\n".join(
                f"- {issue}" for issue in results["unresolved_issues"]
            )

        # Inject reasons compact summary if available
        reasons_summary = reasons_compact(500)
        if reasons_summary:
            usage_for_user += f"\n\nBELIEFS STATE:\n{reasons_summary}"

        # Check for active warnings from reasons
        reasons_warnings = reasons_list_warnings()

        user_result = user(
            results["implementer"],
            task,
            usage_for_user,
            iteration,
            continue_conversations,
        )
        results["user"] = process_agent_output(
            "user", user_result["output"], iteration, no_questions
        )
        results["user_satisfied"] = user_result["satisfied"]
        save_entry(iteration, "user", results["user"])
        print(f"\n{results['user']}\n")

    # Exit gate: handle user escalation (SATISFIED + open issues)
    if user_result.get("verdict", {}).get("escalate"):
        open_issues = user_result["verdict"].get("open_issues", [])
        issue_list = "\n".join(f"- {i}" for i in open_issues)
        human_response = request_human_input(
            "user",
            {
                "needs_human": True,
                "message": f"User declared SATISFIED but listed open issues:\n{issue_list}\n\nAccept or reject?",
            },
            iteration,
            no_questions,
        )
        if human_response and "reject" in human_response.lower():
            results["user_satisfied"] = False

    # Exit gate: SATISFIED + active beliefs WARNINGs
    if results["user_satisfied"] and reasons_warnings:
        print(
            "  [EXIT GATE] User SATISFIED but beliefs system has active WARNINGs — escalating to human"
        )
        human_response = request_human_input(
            "user",
            {
                "needs_human": True,
                "message": f"User declared SATISFIED but beliefs system has active WARNINGs:\n{reasons_warnings}\n\nAccept or reject?",
            },
            iteration,
            no_questions,
        )
        if human_response and "reject" in human_response.lower():
            results["user_satisfied"] = False

    # Create iteration understanding document - what we learned this iteration
    unresolved_section = ""
    if results["unresolved_issues"]:
        unresolved_section = "\n### Unresolved Issues\n\n"
        unresolved_section += "\n".join(
            f"- {issue}" for issue in results["unresolved_issues"]
        )
        unresolved_section += "\n"

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
{unresolved_section}
## Summary

- Reviewer verdict: {'APPROVED' if results['approved'] else 'NEEDS_CHANGES'}
- User verdict: {'SATISFIED' if results['user_satisfied'] else 'NEEDS_IMPROVEMENT'}
- Unresolved issues: {len(results['unresolved_issues'])}
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
    summary_path = save_artifact(
        f"ITERATION_{iteration}_HUMAN_REVIEW.md", human_summary
    )

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
    review_path = get_artifacts_dir() / f"ITERATION_{iteration}_HUMAN_REVIEW.md"
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
            lines = agent_output.split("\n")
            escalation_lines = []
            capturing = False
            for line in lines:
                if any(m in line.upper() for m in escalation_markers):
                    capturing = True
                if capturing:
                    escalation_lines.append(line)
                    if line.strip() == "" and len(escalation_lines) > 1:
                        break
            return {"needs_human": True, "message": "\n".join(escalation_lines)}
    return None


def request_human_input(
    agent_name: str, escalation: dict, iteration: int, no_questions: bool = False
) -> str:
    """Request input from human when agent escalates."""
    print(f"\n{'='*60}")
    print(f"ESCALATION from {agent_name.upper()}")
    print("=" * 60)
    print(f"\n{escalation['message']}\n")

    # Save escalation to file
    escalation_path = get_artifacts_dir() / f"ESCALATION_{iteration}_{agent_name}.md"
    escalation_content = f"""# Escalation from {agent_name}

## Agent's Question/Issue

{escalation['message']}

## Human Response

(Enter your response below)

"""
    escalation_path.write_text(escalation_content)

    # If no_questions mode, auto-respond without waiting for input
    if no_questions:
        auto_response = (
            "(No response provided - agent should proceed with best judgment)"
        )
        print("[--no-questions mode: Auto-responding with default]")
        print(f"Escalation saved to: {escalation_path}")
        return auto_response

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

    response = "\n".join(lines)

    if response.strip():
        # Update file with response
        escalation_content += response
        escalation_path.write_text(escalation_content)
        return response

    # Check if they edited the file instead
    content = escalation_path.read_text()
    if "## Human Response" in content:
        response = content.split("## Human Response")[-1].strip()
        if response:
            return response

    return "(No response provided - agent should proceed with best judgment)"


def run_pipeline(
    task: str,
    max_iterations: int = 3,
    understanding_path: str | None = None,
    continue_conversations: bool = False,
    effort: str = "moderate",
    no_questions: bool = False,
    plan_only: bool = False,
    existing_plan: str | None = None,
) -> dict:
    """Run the development loop with feedback iterations."""

    # Get effort configuration
    effort_config = EFFORT_CONFIGS.get(effort, EFFORT_CONFIGS["moderate"])

    # Override max_iterations from effort level if not explicitly set
    if max_iterations == 3:  # default value
        max_iterations = effort_config["max_iterations"]

    # Start new log session
    log_separator(f"PIPELINE: {task[:50]}")
    log(f"Task: {task}")
    log(f"Effort level: {effort}")
    log(f"Max iterations: {max_iterations}")
    log(f"Continue conversations: {continue_conversations}")
    log(f"Understanding path: {understanding_path}")

    # Initialize .sdlc-loop/ directory structure
    init_sdlc_dir()

    # Initialize reasons database
    reasons_init()

    # Load shared understanding if provided
    shared_understanding = None
    if understanding_path:
        shared_understanding = load_understanding(understanding_path)
        if shared_understanding:
            print(f"Loaded shared understanding from: {understanding_path}")
            # Save to artifacts for reference
            save_artifact("SHARED_UNDERSTANDING.md", shared_understanding)
        else:
            print(f"Warning: No understanding found at: {understanding_path}")

    print("=" * 60)
    print("SUPERVISOR: Starting development loop")
    print(f"TASK: {task}")
    print(f"EFFORT LEVEL: {effort} - {effort_config['description']}")
    print(f"MAX ITERATIONS: {max_iterations}")
    print(f"Repo root: {get_repo_root()}")
    print(f"SDLC dir: {get_sdlc_dir()}")
    print("=" * 60)

    # Save task to artifacts
    save_artifact(
        "TASK.md", f"# Task\n\n{task}\n\nStarted: {datetime.now().isoformat()}"
    )

    # Plan-only mode: run planner and exit
    if plan_only:
        print("\n[PLAN-ONLY MODE] Running planner only...")
        plan_result = planner(
            task, None, shared_understanding, 1, continue_conversations
        )
        plan_output = plan_result["output"]
        save_artifact("PLAN.md", f"# Plan\n\nTask: {task}\n\n{plan_output}")
        print(f"\n{plan_output}\n")
        print(f"\n{'='*60}")
        print("PLAN-ONLY MODE COMPLETE")
        print(f"Plan saved to: {get_artifacts_dir() / 'PLAN.md'}")
        print("Review the plan, then run with --plan PLAN.md to continue")
        print("=" * 60)
        return {
            "repo": str(get_repo_root()),
            "iterations": 0,
            "final_satisfied": False,
            "plan_only": True,
            "plan": plan_output,
        }

    all_results = []
    user_feedback = None

    for i in range(max_iterations):
        iteration = i + 1
        print(f"\n{'='*60}")
        print(f"ITERATION {iteration} of {max_iterations}")
        print("=" * 60)

        # Only use existing_plan for the first iteration
        plan_for_iteration = existing_plan if i == 0 else None

        results = run_iteration(
            task,
            iteration,
            user_feedback,
            shared_understanding,
            continue_conversations,
            max_inner_iterations=effort_config["max_inner_iterations"],
            effort_config=effort_config,
            no_questions=no_questions,
            existing_plan=plan_for_iteration,
        )
        all_results.append(results)

        if results["user_satisfied"]:
            print("\n" + "=" * 60)
            print("SUPERVISOR: User is SATISFIED - development complete!")
            print("=" * 60)
            break

        if i < max_iterations - 1:
            print("\n" + "-" * 60)
            print(
                f"SUPERVISOR: User requested improvements - continuing to iteration {iteration + 1}"
            )
            print("-" * 60)

            # Autonomous mode: just continue with user feedback
            # Human can review checkpoints async via git history
            user_feedback = results["user"]

            # Update cumulative understanding with learnings
            cumulative_path = get_artifacts_dir() / "CUMULATIVE_UNDERSTANDING.md"
            iteration_understanding = (
                get_artifacts_dir() / f"ITERATION_{iteration}_UNDERSTANDING.md"
            ).read_text()

            if cumulative_path.exists():
                cumulative = cumulative_path.read_text()
                cumulative += f"\n\n---\n\n{iteration_understanding}"
            else:
                cumulative = f"# Cumulative Understanding\n\nLearnings accumulated across iterations.\n\n---\n\n{iteration_understanding}"

            cumulative_path.write_text(cumulative)
    else:
        print("\n" + "=" * 60)
        print("SUPERVISOR: Max iterations reached")
        print("=" * 60)

    # Final comprehensive summary for human review
    final_status = "COMPLETE" if all_results[-1]["user_satisfied"] else "INCOMPLETE"

    # Collect all files created
    all_files = set()
    for r in all_results:
        all_files.update(r.get("files_created", []))

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
1. Generated code in the repo
2. Test files (test_*.py)
3. SDLC artifacts in .sdlc-loop/artifacts/

If changes are needed, run another iteration with feedback.
"""
        else:
            final_summary += """The User agent is NOT satisfied. Options:
1. Review the feedback above and run more iterations
2. Provide additional context/understanding
3. Manually address the remaining issues

To continue: `uv run supervisor.py --understanding .sdlc-loop/artifacts/ "task" --max-iterations N`
"""

    save_artifact("FINAL_REPORT.md", final_summary)

    print(f"\n{'='*60}")
    print(f"FINAL REPORT: {get_artifacts_dir() / 'FINAL_REPORT.md'}")
    print(f"{'='*60}")

    return {
        "task": task,
        "iterations": len(all_results),
        "results": all_results,
        "final_satisfied": all_results[-1]["user_satisfied"] if all_results else False,
        "repo": str(get_repo_root()),
    }


def run_continuous(
    queue_path: Path,
    max_iterations: int = 3,
    understanding_path: str | None = None,
    continue_conversations: bool = False,
    effort: str = "moderate",
    no_questions: bool = False,
) -> None:
    """Run the pipeline continuously, processing tasks from a queue file.

    Loops forever until interrupted with Ctrl+C. When the queue is empty,
    sleeps for 60 seconds then checks again.
    """
    print("=" * 60)
    print("SUPERVISOR: Starting continuous mode")
    print(f"Queue file: {queue_path}")
    print(f"Effort level: {effort}")
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
                        continue_conversations=continue_conversations,
                        effort=effort,
                        no_questions=no_questions,
                    )

                    status = "SATISFIED" if result["final_satisfied"] else "INCOMPLETE"
                    print(f"\n[Continuous] Task {tasks_completed} finished: {status}")
                    print(f"[Continuous] Iterations: {result['iterations']}")

                except Exception as e:
                    print(
                        f"\n[Continuous] Task {tasks_completed} failed with error: {e}"
                    )
                    log(f"ERROR in task {tasks_completed}: {e}")

                # Check remaining tasks
                remaining = read_queue(queue_path)
                print(f"[Continuous] Remaining tasks in queue: {len(remaining)}")

            else:
                print(
                    "\n[Continuous] Queue empty. Sleeping 60 seconds... (Ctrl+C to exit)"
                )
                time.sleep(60)

    except KeyboardInterrupt:
        print(f"\n\n{'='*60}")
        print("SUPERVISOR: Continuous mode stopped by user")
        print(f"Tasks completed: {tasks_completed}")
        print("=" * 60)


def main():
    """Main entry point for the ftl-sdlc-loop CLI."""
    # Handle --version
    if "--version" in sys.argv:
        from importlib.metadata import version
        print(f"ftl-sdlc-loop {version('ftl-sdlc-loop')}")
        sys.exit(0)

    # Handle --help / -h explicitly to prevent it being treated as a task
    if "-h" in sys.argv or "--help" in sys.argv:
        print(f"Usage: {sys.argv[0]} <task description> [options]")
        print(f"       {sys.argv[0]} --continuous [options]")
        print("\nOptions:")
        print("  -h, --help            Show this help message and exit")
        print("  --version             Show version and exit")
        print("  --repo PATH           Path to code repository (default: CWD)")
        print(
            "  --effort LEVEL        Effort level: minimal, moderate, maximum (default: moderate)"
        )
        print(
            "  --max-iterations N    Maximum development iterations (default: from effort level)"
        )
        print("  --understanding PATH  Path to understanding file or directory")
        print(
            "  --continue            Continue previous agent conversations (for follow-up runs)"
        )
        print(
            "  --continuous          Run in continuous mode, processing tasks from a queue file"
        )
        print("  --queue PATH          Path to queue file (default: queue.txt)")
        print(
            "  --context-dir PATH    Add read-only reference directory for agents (repeatable)"
        )
        print("  --env PATH            Load .env file variables")
        print(
            "  --prompt-file PATH    Read task description from file instead of command line"
        )
        print(
            "  --plan-only           Run planner only, save plan, and exit for review"
        )
        print("  --plan PATH           Use existing plan file, skip planner stage")
        print(
            "  --push                Push changes to remote"
        )
        print(
            "  --pr                  Create a GitHub pull request instead of pushing directly"
        )
        print(
            "  --no-squash           Don't squash commits when pushing (default: squash)"
        )
        print(
            "  --no-questions        Disable all interactive prompts (auto-respond with defaults)"
        )
        print(
            "  --branch NAME         Working branch for feature development (default: main)"
        )
        print("\nGitHub options:")
        print("  --github-issue NUM    Fetch GitHub issue and use as task prompt")
        print(
            "  --github-repo SLUG    GitHub repo (owner/repo) for issue fetch (auto-detected if omitted)"
        )
        print("  --github-pr           Create GitHub pull request after successful run")
        print(
            "  --code-review         Run code-review review-loop after PR creation (requires --github-pr)"
        )
        print("  --reasons-db PATH     Path to reasons database (from code-expert)")
        print("  --beliefs PATH        Beliefs file for code-review (from code-expert)")
        print(
            "  --review-model NAME   Model for code-review (repeatable, default: claude + gemini)"
        )
        print("\nGitLab options:")
        print(
            "  --gitlab-issue NUM    Fetch GitLab issue, assign to self, use as task prompt"
        )
        print(
            "  --gitlab-mr           Create GitLab merge request after successful run"
        )
        print("  --gitlab-remote URL   Add GitLab remote")
        print("\nEffort levels:")
        print("  minimal  - Fast (~5-15 min): working solution, basic tests")
        print(
            "  moderate - Balanced (~30-60 min): good practices, decent tests (default)"
        )
        print("  maximum  - Production (~2-3 hours): comprehensive testing & docs")
        print("\nThe loop runs autonomously. Human reviews FINAL_REPORT.md at the end.")
        print("\nExamples:")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --repo /path/to/myproject 'add a new feature'")
        print(f"  {sys.argv[0]} --push                     # Push changes")
        print(f"  {sys.argv[0]} --pr                       # Create a PR")
        print(f"  {sys.argv[0]} --max-iterations 5 'complex feature'")
        print(f"  {sys.argv[0]} --continue 'fix the bug identified in the last run'")
        print("\nGitHub workflow:")
        print(
            f"  {sys.argv[0]} --repo ~/myproject --github-issue 42"
        )
        print(
            f"  {sys.argv[0]} --github-pr --push    # Push and create PR"
        )
        print("\nGitLab workflow:")
        print(
            f"  {sys.argv[0]} --repo ~/myproject --gitlab-issue 285"
        )
        print(
            f"  {sys.argv[0]} --gitlab-mr --push   # Push and create MR"
        )
        print("\nContinuous mode:")
        print(f"  {sys.argv[0]} --continuous")
        print(f"  {sys.argv[0]} --continuous --queue my_tasks.txt")
        sys.exit(0)

    # Check for --continuous flag first since it doesn't require a task argument
    has_continuous = "--continuous" in sys.argv

    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <task description> [options]")
        print(f"       {sys.argv[0]} --continuous [options]")
        print("\nRun with -h or --help for full options.")
        print("\nExamples:")
        print(f"  {sys.argv[0]} 'write a function to calculate fibonacci numbers'")
        print(f"  {sys.argv[0]} --repo /path/to/project 'add a new feature'")
        print(f"  {sys.argv[0]} --github-issue 42")
        print(f"  {sys.argv[0]} --continuous")
        sys.exit(1)

    # Parse args
    args = sys.argv[1:]
    max_iterations = 3
    understanding_path = None
    continue_conversations = False
    continuous_mode = False
    queue_path = DEFAULT_QUEUE_PATH
    effort = "moderate"  # default effort level
    no_questions = False  # disable all user prompts
    gitlab_issue_number = None  # GitLab issue to fetch
    gitlab_mr = False  # Create GitLab MR after run
    github_issue_number = None  # GitHub issue to fetch
    github_issue_repo = None  # GitHub repo slug (owner/repo)
    github_pr = False  # Create GitHub PR after run
    code_review = False  # Run code-review after PR creation
    beliefs_path = None  # Beliefs file for code-review
    reasons_db_path = None  # Reasons database path
    review_models = []  # Models to use for code-review (e.g. claude, gemini)
    repo_path = None  # Code repo path from --repo
    branch_name = None  # Override branch name

    if "--repo" in args:
        idx = args.index("--repo")
        repo_path = os.path.abspath(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if "--effort" in args:
        idx = args.index("--effort")
        effort = args[idx + 1]
        if effort not in EFFORT_CONFIGS:
            print(
                f"Error: Invalid effort level '{effort}'. Must be one of: {', '.join(EFFORT_CONFIGS.keys())}"
            )
            sys.exit(1)
        args = args[:idx] + args[idx + 2 :]

    if "--no-questions" in args:
        idx = args.index("--no-questions")
        no_questions = True
        args = args[:idx] + args[idx + 1 :]

    # GitLab integration flags
    if "--gitlab-issue" in args:
        idx = args.index("--gitlab-issue")
        gitlab_issue_number = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]
        # Check glab is installed
        if not check_glab_installed():
            print("Error: glab CLI is not installed or not authenticated.")
            print("Install: https://gitlab.com/gitlab-org/cli")
            print("Authenticate: glab auth login")
            sys.exit(1)

    if "--gitlab-mr" in args:
        idx = args.index("--gitlab-mr")
        gitlab_mr = True
        args = args[:idx] + args[idx + 1 :]
        # Check glab is installed
        if not check_glab_installed():
            print("Error: glab CLI is not installed or not authenticated.")
            print("Install: https://gitlab.com/gitlab-org/cli")
            print("Authenticate: glab auth login")
            sys.exit(1)

    # GitHub integration flags
    if "--github-issue" in args:
        idx = args.index("--github-issue")
        github_issue_number = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]
        if not check_gh_installed():
            print("Error: gh CLI is not installed or not authenticated.")
            print("Install: https://cli.github.com")
            print("Authenticate: gh auth login")
            sys.exit(1)

    if "--github-repo" in args:
        idx = args.index("--github-repo")
        github_issue_repo = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if "--github-pr" in args:
        idx = args.index("--github-pr")
        github_pr = True
        args = args[:idx] + args[idx + 1 :]
        if not check_gh_installed():
            print("Error: gh CLI is not installed or not authenticated.")
            print("Install: https://cli.github.com")
            print("Authenticate: gh auth login")
            sys.exit(1)

    if "--code-review" in args:
        idx = args.index("--code-review")
        code_review = True
        args = args[:idx] + args[idx + 1 :]

    if "--reasons-db" in args:
        idx = args.index("--reasons-db")
        reasons_db_path = os.path.expanduser(args[idx + 1])
        if not os.path.isfile(reasons_db_path):
            print(f"Error: Reasons database not found: {reasons_db_path}")
            print("  --reasons-db expects a pre-built database (e.g. from code-expert).")
            print("  Omit this flag to auto-create a new database at .sdlc-loop/reasons.db.")
            sys.exit(1)
        args = args[:idx] + args[idx + 2 :]

    if "--beliefs" in args:
        idx = args.index("--beliefs")
        beliefs_path = os.path.expanduser(args[idx + 1])
        if not os.path.isfile(beliefs_path):
            print(f"Error: Beliefs file not found: {beliefs_path}")
            sys.exit(1)
        args = args[:idx] + args[idx + 2 :]

    while "--review-model" in args:
        idx = args.index("--review-model")
        review_models.append(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if "--branch" in args:
        idx = args.index("--branch")
        branch_name = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    # GitLab remote URL (for bare repo workflows)
    gitlab_remote_url = None
    if "--gitlab-remote" in args:
        idx = args.index("--gitlab-remote")
        gitlab_remote_url = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    # Set the repo root (defaults to CWD)
    if repo_path:
        set_repo_root(Path(repo_path))

    # Set the target branch (default: main)
    if branch_name:
        set_target_branch(branch_name)

    # Set external reasons database if provided
    if reasons_db_path:
        set_reasons_db(Path(reasons_db_path))

    # Add GitLab remote if specified
    repo = get_repo_root()
    env = os.environ.copy()
    env.pop("CLAUDECODE", None)
    if gitlab_remote_url:
        existing = subprocess.run(
            ["git", "remote", "get-url", "gitlab"],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        if existing.returncode != 0:
            subprocess.run(
                ["git", "remote", "add", "gitlab", gitlab_remote_url],
                cwd=repo, env=env, capture_output=True,
            )
            print(f"  Added 'gitlab' remote: {gitlab_remote_url}")
        elif existing.stdout.strip() != gitlab_remote_url:
            subprocess.run(
                ["git", "remote", "set-url", "gitlab", gitlab_remote_url],
                cwd=repo, env=env, capture_output=True,
            )
            print(f"  Updated 'gitlab' remote: {gitlab_remote_url}")
    if github_issue_repo:
        github_url = f"git@github.com:{github_issue_repo}.git"
        existing = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo, env=env, capture_output=True, text=True,
        )
        if existing.returncode != 0 or existing.stdout.strip() != github_url:
            subprocess.run(
                ["git", "remote", "set-url", "origin", github_url],
                cwd=repo, env=env, capture_output=True,
            )
            print(f"  Set origin to: {github_url}")

    # Handle --context-dir (repeatable, read-only reference directories for agents)
    context_dirs = []
    while "--context-dir" in args:
        idx = args.index("--context-dir")
        context_dirs.append(os.path.abspath(args[idx + 1]))
        args = args[:idx] + args[idx + 2:]
    if context_dirs:
        set_context_dirs(context_dirs)
        print(f"  Context directories: {', '.join(context_dirs)}")

    # Handle --env early (load environment variables before running agents)
    if "--env" in args:
        idx = args.index("--env")
        env_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]
        success = load_env_file(env_path)
        if not success:
            sys.exit(1)

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
        success = push_workspace(
            branch=get_target_branch(), create_pr=create_pr, squash=squash
        )
        sys.exit(0 if success else 1)

    if "--max-iterations" in args:
        idx = args.index("--max-iterations")
        max_iterations = int(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    if "--understanding" in args:
        idx = args.index("--understanding")
        understanding_path = args[idx + 1]
        args = args[:idx] + args[idx + 2 :]

    if "--continue" in args:
        idx = args.index("--continue")
        continue_conversations = True
        args = args[:idx] + args[idx + 1 :]

    if "--continuous" in args:
        idx = args.index("--continuous")
        continuous_mode = True
        args = args[:idx] + args[idx + 1 :]

    if "--queue" in args:
        idx = args.index("--queue")
        queue_path = Path(args[idx + 1])
        args = args[:idx] + args[idx + 2 :]

    # Handle --prompt-file (read task from file)
    prompt_file = None
    if "--prompt-file" in args:
        idx = args.index("--prompt-file")
        prompt_file = Path(args[idx + 1]).expanduser()
        args = args[:idx] + args[idx + 2 :]
        if not prompt_file.exists():
            print(f"Error: Prompt file not found: {prompt_file}")
            sys.exit(1)

    # Handle --plan-only (run planner and exit)
    plan_only = False
    if "--plan-only" in args:
        idx = args.index("--plan-only")
        plan_only = True
        args = args[:idx] + args[idx + 1 :]

    # Handle --plan PATH (use existing plan, skip planner)
    existing_plan = None
    if "--plan" in args:
        idx = args.index("--plan")
        plan_path = Path(args[idx + 1]).expanduser()
        args = args[:idx] + args[idx + 2 :]
        if not plan_path.exists():
            print(f"Error: Plan file not found: {plan_path}")
            sys.exit(1)
        existing_plan = plan_path.read_text()
        print(f"Using existing plan from: {plan_path}")

    # Handle GitLab issue - fetch and use as task
    # Note: glab needs to run from within a git repo with GitLab remote
    gitlab_issue = None
    if gitlab_issue_number:
        repo = get_repo_root()
        if not repo.exists() or not (repo / ".git").exists():
            print("Error: Not a git repository. Use --repo to specify a repo path.")
            sys.exit(1)
        print(f"Fetching GitLab issue #{gitlab_issue_number}...")
        gitlab_issue = gitlab_fetch_issue(gitlab_issue_number, cwd=repo)
        if not gitlab_issue:
            print(f"Error: Could not fetch GitLab issue #{gitlab_issue_number}")
            sys.exit(1)
        print(f"Issue: {gitlab_issue['title']}")
        # Assign to self
        gitlab_assign_issue(gitlab_issue_number, cwd=repo)
        # Generate branch name if not specified
        if not branch_name:
            branch_name = gitlab_branch_name(gitlab_issue)
            print(f"Branch: {branch_name}")
        # Create feature branch
        set_target_branch(branch_name)
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        subprocess.run(
            ["git", "checkout", "-B", branch_name],
            cwd=repo,
            env=env,
            capture_output=True,
        )

    # Handle GitHub issue - fetch and use as task
    github_issue = None
    if github_issue_number:
        repo = get_repo_root()
        if not repo.exists() or not (repo / ".git").exists():
            print("Error: Not a git repository. Use --repo to specify a repo path.")
            sys.exit(1)
        print(f"Fetching GitHub issue #{github_issue_number}...")
        github_issue = github_fetch_issue(
            github_issue_number, repo=github_issue_repo, cwd=repo
        )
        if not github_issue:
            print(f"Error: Could not fetch GitHub issue #{github_issue_number}")
            sys.exit(1)
        print(f"Issue: {github_issue['title']}")
        # Generate branch name if not specified
        if not branch_name:
            branch_name = github_branch_name(github_issue)
            print(f"Branch: {branch_name}")
        # Create feature branch
        set_target_branch(branch_name)
        env = os.environ.copy()
        env.pop("CLAUDECODE", None)
        subprocess.run(
            ["git", "checkout", "-B", branch_name],
            cwd=repo,
            env=env,
            capture_output=True,
        )

    if continuous_mode:
        # Run in continuous mode
        run_continuous(
            queue_path=queue_path,
            max_iterations=max_iterations,
            understanding_path=understanding_path,
            continue_conversations=continue_conversations,
            effort=effort,
            no_questions=no_questions,
        )
    else:
        # Run single task - from issue, file, or command line
        if gitlab_issue:
            task = gitlab_build_prompt(gitlab_issue)
            print(f"Using GitLab issue #{gitlab_issue_number} as task")
        elif github_issue:
            task = github_build_prompt(github_issue)
            print(f"Using GitHub issue #{github_issue_number} as task")
        elif prompt_file:
            task = prompt_file.read_text().strip()
            print(f"Read task from: {prompt_file}")
        else:
            task = " ".join(args)
        if not task:
            print(
                "Error: No task specified. Use --github-issue, --gitlab-issue, --prompt-file, --continuous, or provide a task."
            )
            sys.exit(1)

        result = run_pipeline(
            task,
            max_iterations,
            understanding_path,
            continue_conversations,
            effort,
            no_questions,
            plan_only=plan_only,
            existing_plan=existing_plan,
        )

        print(f"\nRepo: {result['repo']}")
        if result.get("plan_only"):
            print(
                "Plan-only mode completed. Review the plan and run with --plan to continue."
            )
        else:
            print("Run 'git log --oneline' to see the commit history.")

        # Handle GitLab MR creation
        if gitlab_mr and result.get("final_satisfied"):
            print("\nCreating GitLab merge request...")
            repo = get_repo_root()
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)

            mr_branch = branch_name or "ftl-sdlc-work"

            if not branch_name:
                subprocess.run(
                    ["git", "checkout", "-B", mr_branch],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )

            # Squash all commits into one clean commit
            sq_result = subprocess.run(
                ["git", "log", "--oneline", "origin/main..HEAD"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            commit_count = len([l for l in sq_result.stdout.strip().split("\n") if l])
            if commit_count > 1:
                mr_title = gitlab_issue["title"] if gitlab_issue else task[:70]
                print(f"Squashing {commit_count} commits...")
                subprocess.run(
                    ["git", "reset", "--soft", "origin/main"],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )
                commit_msg = (
                    f"{mr_title}\n\nCloses #{gitlab_issue['number']}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
                    if gitlab_issue
                    else f"{mr_title}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
                )
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )

            # Push the branch
            print(f"Pushing branch {mr_branch}...")
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", mr_branch],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                print(f"Error pushing branch: {push_result.stderr}")
            else:
                mr_title = gitlab_issue["title"] if gitlab_issue else task[:70]

                mr_template_path = gitlab_find_mr_template(repo)
                if mr_template_path:
                    print(f"Using MR template: {mr_template_path}")
                    template_content = mr_template_path.read_text()
                    mr_description = gitlab_fill_mr_template(
                        template_content=template_content,
                        task=task,
                        gitlab_issue=gitlab_issue,
                        workspace=repo,
                    )
                else:
                    mr_description = f"## Description\n\n{task[:500]}\n\n"
                    if gitlab_issue:
                        mr_description += f"Closes #{gitlab_issue['number']}\n\n"
                    mr_description += "🤖 Generated with [ftl-sdlc-loop](https://github.com/benthomasson/ftl-sdlc-loop)"

                mr_url = gitlab_create_mr(
                    source_branch=mr_branch,
                    title=mr_title,
                    description=mr_description,
                    target_branch="main",
                    assignee=gitlab_get_username(),
                    cwd=repo,
                )
                if mr_url:
                    print(f"Merge request created: {mr_url}")
        elif gitlab_mr and not result.get("final_satisfied"):
            print("\nSkipping MR creation - pipeline did not complete successfully")

        # Handle GitHub PR creation
        if github_pr and result.get("final_satisfied"):
            print("\nCreating GitHub pull request...")
            repo = get_repo_root()
            env = os.environ.copy()
            env.pop("CLAUDECODE", None)

            pr_branch = branch_name or "ftl-sdlc-work"

            if not branch_name:
                subprocess.run(
                    ["git", "checkout", "-B", pr_branch],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )

            # Squash all commits into one clean commit
            sq_result = subprocess.run(
                ["git", "log", "--oneline", "origin/main..HEAD"],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            commit_count = len([l for l in sq_result.stdout.strip().split("\n") if l])
            if commit_count > 1:
                pr_title = github_issue["title"] if github_issue else task[:70]
                print(f"Squashing {commit_count} commits...")
                subprocess.run(
                    ["git", "reset", "--soft", "origin/main"],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )
                commit_msg = (
                    f"{pr_title}\n\nCloses #{github_issue['number']}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
                    if github_issue
                    else f"{pr_title}\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
                )
                subprocess.run(
                    ["git", "commit", "-m", commit_msg],
                    cwd=repo,
                    env=env,
                    capture_output=True,
                )

            # Check if there are actual code changes
            diff_check = subprocess.run(
                ["git", "diff", "--stat", "origin/main..HEAD"],
                cwd=repo, env=env, capture_output=True, text=True
            )
            if not diff_check.stdout.strip():
                print("No code changes to push — skipping PR creation.")
                return

            print(f"Pushing branch {pr_branch}...")
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", pr_branch],
                cwd=repo,
                env=env,
                capture_output=True,
                text=True,
            )
            if push_result.returncode != 0:
                print(f"Error pushing branch: {push_result.stderr}")
            else:
                pr_title = github_issue["title"] if github_issue else task[:70]
                pr_description = github_fill_pr_template(
                    task=task, github_issue=github_issue, workspace=repo
                )

                repo_flag = ["--repo", github_issue_repo] if github_issue_repo else []
                pr_result = subprocess.run(
                    [
                        "gh",
                        "pr",
                        "create",
                        "--title",
                        pr_title,
                        "--body",
                        pr_description,
                        "--base",
                        "main",
                        "--head",
                        pr_branch,
                    ]
                    + repo_flag,
                    cwd=repo,
                    env=env,
                    capture_output=True,
                    text=True,
                )
                if pr_result.returncode == 0:
                    pr_url = pr_result.stdout.strip()
                    print(f"Pull request created: {pr_url}")

                    # Run code-review if requested
                    if code_review:
                        print(f"\nRunning code-review review-loop on {pr_url}...")
                        review_cmd = [
                            "code-review",
                            "review-loop",
                            "--pr",
                            pr_url,
                            "--comment",
                        ]
                        review_cmd.extend(["--repo", str(repo)])
                        if github_issue_repo and github_issue_number:
                            issue_ref = f"https://github.com/{github_issue_repo}/issues/{github_issue_number}"
                            review_cmd.extend(["--github-issue", issue_ref])
                        if beliefs_path:
                            review_cmd.extend(["--beliefs", beliefs_path])
                        for model in review_models:
                            review_cmd.extend(["-m", model])
                        review_result = subprocess.run(
                            review_cmd, env=env, capture_output=False
                        )
                        if review_result.returncode != 0:
                            print(
                                f"Code review completed with exit code {review_result.returncode}"
                            )
                else:
                    print(f"Error creating PR: {pr_result.stderr}")
        elif github_pr and not result.get("final_satisfied"):
            print("\nSkipping PR creation - pipeline did not complete successfully")


if __name__ == "__main__":
    main()
