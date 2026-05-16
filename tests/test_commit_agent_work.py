"""Tests for commit_agent_work staging behavior.

Uses real git repos in temp directories to verify that source-modifying agents
(implementer, tester) commit source file changes while excluding .sdlc-loop/,
and non-source-modifying agents (planner, reviewer) produce no commits since
their outputs go to gitignored .sdlc-loop/artifacts/.
"""

import subprocess
from pathlib import Path
from unittest.mock import patch


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in the given directory."""
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env={
            "GIT_AUTHOR_NAME": "test",
            "GIT_AUTHOR_EMAIL": "test@test",
            "GIT_COMMITTER_NAME": "test",
            "GIT_COMMITTER_EMAIL": "test@test",
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create a git repo with source code and .sdlc-loop/ gitignored."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(["init"], repo)
    _git(["config", "user.email", "test@test"], repo)
    _git(["config", "user.name", "test"], repo)
    (repo / "src").mkdir()
    (repo / "src" / "main.py").write_text("print('hello')\n")
    (repo / ".gitignore").write_text(".sdlc-loop/\n")
    # Create .sdlc-loop structure
    sdlc = repo / ".sdlc-loop"
    (sdlc / "artifacts" / "planner").mkdir(parents=True)
    (sdlc / "artifacts" / "implementer").mkdir(parents=True)
    (sdlc / "artifacts" / "reviewer").mkdir(parents=True)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "initial"], repo)
    return repo


def _committed_files(repo: Path) -> list[str]:
    """Return list of files changed in the last commit."""
    result = _git(["diff", "--name-only", "HEAD~1", "HEAD"], repo)
    return sorted(result.stdout.strip().split("\n")) if result.stdout.strip() else []


def test_implementer_commits_source_files(tmp_path):
    """Implementer should commit source file changes."""
    repo = _init_repo(tmp_path)

    (repo / "src" / "main.py").write_text("print('modified')\n")

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("implementer", "test commit")

    assert result is True
    files = _committed_files(repo)
    assert "src/main.py" in files


def test_implementer_excludes_sdlc_loop(tmp_path):
    """Implementer should not commit files under .sdlc-loop/."""
    repo = _init_repo(tmp_path)

    (repo / "src" / "main.py").write_text("print('modified')\n")
    (repo / ".sdlc-loop" / "artifacts" / "implementer" / "notes.md").write_text("notes\n")

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("implementer", "test commit")

    assert result is True
    files = _committed_files(repo)
    assert "src/main.py" in files
    for f in files:
        assert not f.startswith(".sdlc-loop/")


def test_tester_commits_source_files(tmp_path):
    """Tester should commit source and test file changes."""
    repo = _init_repo(tmp_path)
    (repo / "tests").mkdir(exist_ok=True)

    (repo / "src" / "main.py").write_text("print('tested')\n")
    (repo / "tests" / "test_main.py").write_text("def test_it(): pass\n")

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("tester", "test commit")

    assert result is True
    files = _committed_files(repo)
    assert "src/main.py" in files
    assert "tests/test_main.py" in files


def test_planner_returns_false(tmp_path):
    """Planner is not a source-modifying role — commit_agent_work returns False."""
    repo = _init_repo(tmp_path)

    (repo / ".sdlc-loop" / "artifacts" / "planner" / "PLAN.md").write_text("the plan\n")

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("planner", "test commit")

    assert result is False


def test_reviewer_returns_false(tmp_path):
    """Reviewer is not a source-modifying role — commit_agent_work returns False."""
    repo = _init_repo(tmp_path)

    (repo / ".sdlc-loop" / "artifacts" / "reviewer" / "REVIEW.md").write_text("review\n")

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("reviewer", "test commit")

    assert result is False


def test_no_changes_returns_false(tmp_path):
    """commit_agent_work should return False when there are no source changes."""
    repo = _init_repo(tmp_path)

    with patch("ftl_sdlc_loop.agent.get_repo_root", return_value=repo):
        from ftl_sdlc_loop.agent import commit_agent_work

        result = commit_agent_work("implementer", "nothing to commit")

    assert result is False
