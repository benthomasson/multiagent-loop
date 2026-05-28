"""Tests for reasons.py CLI wrapper module."""

from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

from ftl_sdlc_loop.reasons import (
    get_reasons_db,
    set_reasons_db,
    _run_reasons,
    reasons_init,
    reasons_add,
    reasons_compact,
    reasons_list_warnings,
    reasons_search,
    reasons_list_gated,
    reasons_retract,
)


def test_get_reasons_db_default():
    """Default DB path is .sdlc-loop/reasons.db under repo root."""
    with patch("ftl_sdlc_loop.reasons._reasons_db", None):
        with patch("ftl_sdlc_loop.reasons.get_sdlc_dir", return_value=Path("/repo/.sdlc-loop")):
            assert get_reasons_db() == Path("/repo/.sdlc-loop/reasons.db")


def test_get_reasons_db_custom():
    """set_reasons_db overrides the default path."""
    custom = Path("/tmp/custom.db")
    set_reasons_db(custom)
    try:
        assert get_reasons_db() == custom
    finally:
        set_reasons_db(None)


def test_run_reasons_constructs_command():
    """_run_reasons prepends 'reasons --db PATH' to args."""
    mock_result = subprocess.CompletedProcess([], 0, "output", "")
    with patch("ftl_sdlc_loop.reasons._reasons_db", Path("/tmp/test.db")):
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            with patch("ftl_sdlc_loop.reasons._find_reasons_bin", return_value="reasons"):
                _run_reasons("search", "query")
                cmd = mock_run.call_args[0][0]
                assert cmd[0] == "reasons"
                assert cmd[1:3] == ["--db", "/tmp/test.db"]
                assert cmd[3:] == ["search", "query"]


def test_run_reasons_handles_not_found():
    """_run_reasons returns error result when CLI is not installed."""
    with patch("ftl_sdlc_loop.reasons._reasons_db", Path("/tmp/test.db")):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            with patch("ftl_sdlc_loop.reasons._find_reasons_bin", return_value="reasons"):
                result = _run_reasons("search", "test")
                assert result.returncode == 1
                assert "not found" in result.stderr


def test_run_reasons_handles_timeout():
    """_run_reasons returns error result on timeout."""
    with patch("ftl_sdlc_loop.reasons._reasons_db", Path("/tmp/test.db")):
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(["reasons"], 60)):
            with patch("ftl_sdlc_loop.reasons._find_reasons_bin", return_value="reasons"):
                result = _run_reasons("compact")
                assert result.returncode == 1
                assert "timeout" in result.stderr


def test_reasons_init_skips_existing(tmp_path):
    """reasons_init does nothing if the DB already exists."""
    db = tmp_path / "reasons.db"
    db.write_text("existing")
    with patch("ftl_sdlc_loop.reasons._reasons_db", db):
        with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
            reasons_init()
            mock.assert_not_called()


def test_reasons_init_creates_new(tmp_path):
    """reasons_init calls 'reasons init' when DB does not exist."""
    db = tmp_path / "reasons.db"
    with patch("ftl_sdlc_loop.reasons._reasons_db", db):
        with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
            reasons_init()
            mock.assert_called_once_with("init")


def test_reasons_add_basic():
    """reasons_add constructs correct CLI args for basic add."""
    with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
        reasons_add("plan-1-1", "Use REST API", label="AXIOM")
        mock.assert_called_once_with(
            "add", "plan-1-1", "Use REST API", "--label", "AXIOM"
        )


def test_reasons_add_with_deps_and_source():
    """reasons_add includes --sl and --source when provided."""
    with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
        reasons_add(
            "impl-1-foo.py",
            "Implements handler",
            label="DERIVED",
            depends_on=["plan-1-1", "plan-1-2"],
            source="foo.py",
        )
        mock.assert_called_once_with(
            "add", "impl-1-foo.py", "Implements handler",
            "--label", "DERIVED",
            "--sl", "plan-1-1,plan-1-2",
            "--source", "foo.py",
        )


def test_reasons_compact_returns_output():
    """reasons_compact returns stdout when present."""
    mock_result = subprocess.CompletedProcess([], 0, "summary text", "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_compact(500) == "summary text"


def test_reasons_compact_returns_none_on_empty():
    """reasons_compact returns None when stdout is empty."""
    mock_result = subprocess.CompletedProcess([], 0, "", "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_compact() is None


def test_reasons_list_warnings_filters():
    """reasons_list_warnings returns only lines containing 'warn'."""
    output = "review-warn-1-1 | WARNING | Some issue\nplan-1-1 | AXIOM | Decision\n"
    mock_result = subprocess.CompletedProcess([], 0, output, "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        result = reasons_list_warnings()
        assert result is not None
        assert "WARNING" in result
        assert "AXIOM" not in result


def test_reasons_list_warnings_none_when_no_warnings():
    """reasons_list_warnings returns None when no warning lines found."""
    output = "plan-1-1 | AXIOM | Decision\nimpl-1-1 | DERIVED | Code\n"
    mock_result = subprocess.CompletedProcess([], 0, output, "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_list_warnings() is None


def test_reasons_search_returns_output():
    """reasons_search returns stdout."""
    mock_result = subprocess.CompletedProcess([], 0, "found: result", "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_search("test") == "found: result"


def test_reasons_search_returns_none_on_empty():
    """reasons_search returns None when no results."""
    mock_result = subprocess.CompletedProcess([], 0, "", "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_search("nonexistent") is None


def test_reasons_retract_basic():
    """reasons_retract constructs correct CLI args."""
    with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
        reasons_retract("plan-1-1")
        mock.assert_called_once_with("retract", "plan-1-1")


def test_reasons_retract_with_reason():
    """reasons_retract includes --reason when provided."""
    with patch("ftl_sdlc_loop.reasons._run_reasons") as mock:
        reasons_retract("plan-1-1", reason="No longer valid")
        mock.assert_called_once_with("retract", "plan-1-1", "--reason", "No longer valid")


def test_reasons_list_gated_returns_output():
    """reasons_list_gated returns stdout."""
    mock_result = subprocess.CompletedProcess([], 0, "gated: node-1", "")
    with patch("ftl_sdlc_loop.reasons._run_reasons", return_value=mock_result):
        assert reasons_list_gated() == "gated: node-1"
