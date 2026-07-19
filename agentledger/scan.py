"""Git-history ingestion for AgentLedger decision units."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Literal


MAX_DIFF_HUNK_CHARS = 12_000


class GitScanError(RuntimeError):
    """Raised when a repository cannot be scanned with Git."""


@dataclass(frozen=True)
class DecisionUnit:
    """One changed file from one commit, ready for later pipeline stages."""

    commit_sha: str
    file_path: str
    diff_hunk: str
    commit_message: str
    author: str
    timestamp: str
    rationale: str | None
    rationale_source: Literal["commit_message", "gpt-5.6-inferred"]


@dataclass(frozen=True)
class _CommitMetadata:
    sha: str
    author: str
    timestamp: str
    message: str


def scan_repository(path: str | Path, since: str | None = None) -> list[DecisionUnit]:
    """Return one decision unit for every changed file in matching commits.

    ``path`` may be a repository root, a directory inside a repository, or a
    tracked file. A nested path limits the scan to its history. ``since`` uses
    Git's ``<ref>..HEAD`` range, so the referenced commit itself is excluded.
    """
    repo_root, pathspec = _resolve_repository_and_pathspec(path)
    commits = _commits_for_range(repo_root, pathspec, since)
    decision_units: list[DecisionUnit] = []

    for commit in commits:
        for file_path in _changed_files(repo_root, commit.sha, pathspec):
            diff_hunk = _diff_for_file(repo_root, commit.sha, file_path)
            decision_units.append(
                DecisionUnit(
                    commit_sha=commit.sha,
                    file_path=file_path,
                    diff_hunk=_truncate_diff(diff_hunk),
                    commit_message=commit.message,
                    author=commit.author,
                    timestamp=commit.timestamp,
                    rationale=None,
                    rationale_source="commit_message",
                )
            )

    return decision_units


def _resolve_repository_and_pathspec(path: str | Path) -> tuple[Path, str | None]:
    target = Path(path).resolve()
    git_directory = target if target.is_dir() else target.parent
    repo_root = Path(_git(git_directory, "rev-parse", "--show-toplevel").strip())

    try:
        relative_target = target.relative_to(repo_root)
    except ValueError as error:
        raise GitScanError(f"{target} is not inside repository {repo_root}") from error

    if relative_target == Path("."):
        return repo_root, None
    return repo_root, relative_target.as_posix()


def _commits_for_range(
    repo_root: Path, pathspec: str | None, since: str | None
) -> list[_CommitMetadata]:
    arguments = [
        "log",
        "-z",
        "--format=%H%x00%an%x00%aI%x00%B%x00",
        "--no-renames",
    ]
    if since:
        arguments.append(f"{since}..HEAD")
    if pathspec:
        arguments.extend(["--", pathspec])

    records = _git(repo_root, *arguments).split("\x00\x00")
    if records and records[-1] == "":
        records.pop()

    if not records:
        return []
    parsed_records = [record.split("\x00", maxsplit=3) for record in records]
    if any(len(record) != 4 for record in parsed_records):
        raise GitScanError("Git returned malformed commit metadata.")

    return [
        _CommitMetadata(
            sha=record[0],
            author=record[1],
            timestamp=record[2],
            message=record[3].strip(),
        )
        for record in parsed_records
    ]


def _changed_files(repo_root: Path, sha: str, pathspec: str | None) -> list[str]:
    arguments = ["diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "--no-renames", sha]
    if pathspec:
        arguments.extend(["--", pathspec])
    return [file_path for file_path in _git(repo_root, *arguments).splitlines() if file_path]


def _diff_for_file(repo_root: Path, sha: str, file_path: str) -> str:
    return _git(
        repo_root,
        "show",
        "--format=",
        "--patch",
        "--no-ext-diff",
        "--no-renames",
        sha,
        "--",
        file_path,
    )


def _truncate_diff(diff_hunk: str) -> str:
    if len(diff_hunk) <= MAX_DIFF_HUNK_CHARS:
        return diff_hunk
    return f"{diff_hunk[:MAX_DIFF_HUNK_CHARS]}\n... [truncated by AgentLedger]\n"


def _git(directory: Path, *arguments: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), *arguments],
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as error:
        raise GitScanError("Git is required to scan repository history.") from error
    except subprocess.CalledProcessError as error:
        message = error.stderr.strip() or error.stdout.strip() or "Git command failed."
        raise GitScanError(message) from error
    return result.stdout
