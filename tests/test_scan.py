"""Integration tests for git-history scanning."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest
from typer.testing import CliRunner

from agentledger.cli import app
from agentledger.scan import GitScanError, scan_repository


def _git(repo: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _commit(repo: Path, message: str, timestamp: str) -> str:
    commit_environment = {
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_COMMITTER_DATE": timestamp,
    }
    _git(repo, "commit", "-m", message, env=commit_environment)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def git_repo(tmp_path: Path) -> dict[str, str | Path]:
    repo = tmp_path / "fixture-repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Test Author")
    _git(repo, "config", "user.email", "test@example.com")

    source_file = repo / "src" / "app.py"
    source_file.parent.mkdir()
    source_file.write_text("VERSION = 1\n", encoding="utf-8")
    docs_file = repo / "docs" / "guide.md"
    docs_file.parent.mkdir()
    docs_file.write_text("# Guide\n", encoding="utf-8")
    _git(repo, "add", ".")
    initial_sha = _commit(repo, "Add initial application files", "2026-01-01T12:00:00+0000")

    source_file.write_text("VERSION = 2\nVALIDATE_EMPTY_PAYLOADS = True\n", encoding="utf-8")
    docs_file.write_text("# Guide\n\nValidation now rejects empty payloads.\n", encoding="utf-8")
    _git(repo, "add", ".")
    second_sha = _commit(
        repo,
        "Harden request validation\n\nReject empty payloads before processing requests.",
        "2026-01-02T12:00:00+0000",
    )

    return {"repo": repo, "initial_sha": initial_sha, "second_sha": second_sha}


def test_scan_returns_one_decision_unit_per_changed_file(git_repo: dict[str, str | Path]) -> None:
    units = scan_repository(git_repo["repo"])

    assert len(units) == 4
    second_commit_units = [unit for unit in units if unit.commit_sha == git_repo["second_sha"]]
    assert {unit.file_path for unit in second_commit_units} == {"docs/guide.md", "src/app.py"}

    source_unit = next(unit for unit in second_commit_units if unit.file_path == "src/app.py")
    assert source_unit.commit_message == (
        "Harden request validation\n\nReject empty payloads before processing requests."
    )
    assert source_unit.author == "Test Author"
    assert source_unit.timestamp == "2026-01-02T12:00:00Z"
    assert "+VALIDATE_EMPTY_PAYLOADS = True" in source_unit.diff_hunk
    assert source_unit.rationale is None
    assert source_unit.rationale_source == "commit_message"


def test_scan_since_excludes_the_referenced_commit(git_repo: dict[str, str | Path]) -> None:
    units = scan_repository(git_repo["repo"], since=str(git_repo["initial_sha"]))

    assert len(units) == 2
    assert {unit.commit_sha for unit in units} == {git_repo["second_sha"]}


def test_scan_limits_history_to_a_nested_path(git_repo: dict[str, str | Path]) -> None:
    source_directory = Path(git_repo["repo"]) / "src"

    units = scan_repository(source_directory)

    assert len(units) == 2
    assert {unit.file_path for unit in units} == {"src/app.py"}


def test_scan_command_serializes_decision_units(git_repo: dict[str, str | Path]) -> None:
    result = CliRunner().invoke(app, ["scan", str(git_repo["repo"]), "--since", str(git_repo["initial_sha"])])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {unit["file_path"] for unit in payload} == {"docs/guide.md", "src/app.py"}
    assert {unit["commit_sha"] for unit in payload} == {git_repo["second_sha"]}


def test_scan_explains_when_path_is_not_a_git_repository(tmp_path: Path) -> None:
    non_repository = tmp_path / "not-a-repository"
    non_repository.mkdir()

    with pytest.raises(GitScanError, match="not inside a Git repository"):
        scan_repository(non_repository)

    result = CliRunner().invoke(app, ["scan", str(non_repository)])

    assert result.exit_code == 1
    assert "scan failed:" in result.stdout
    assert "not inside a Git repository" in result.stdout


def test_scan_explains_when_repository_has_no_commits(tmp_path: Path) -> None:
    repository = tmp_path / "empty-repository"
    repository.mkdir()
    _git(repository, "init")

    with pytest.raises(GitScanError, match="has no commits to scan"):
        scan_repository(repository)

    result = CliRunner().invoke(app, ["scan", str(repository)])

    assert result.exit_code == 1
    assert "has no commits to scan" in result.stdout


def test_demo_scan_runs_without_a_repository_or_api_key() -> None:
    result = CliRunner().invoke(app, ["--demo", "scan"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert {unit["file_path"] for unit in payload} == {
        "src/auth/session.py",
        "docs/getting-started.md",
    }
