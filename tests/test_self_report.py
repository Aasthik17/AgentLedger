"""Tests for auditing AgentLedger's own build history."""

from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace

from rich.console import Console
from typer.testing import CliRunner

from agentledger.cli import SelfReportResult, app, run_self_report


def _git(repository: Path, *arguments: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    return result.stdout.strip()


def _commit(repository: Path, subject: str, timestamp: str) -> None:
    environment = {
        "GIT_AUTHOR_NAME": "Test Author",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_AUTHOR_DATE": timestamp,
        "GIT_COMMITTER_NAME": "Test Author",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_COMMITTER_DATE": timestamp,
    }
    _git(repository, "commit", "-m", subject, env=environment)


class _FakeResponses:
    def create(self, **kwargs: object) -> SimpleNamespace:
        request = json.loads(kwargs["input"][1]["content"])
        return SimpleNamespace(
            output_text=json.dumps(
                {
                    "rationales": [
                        {
                            "unit_id": unit["unit_id"],
                            "rationale": f"Infer why {unit['file_path']} changed.",
                        }
                        for unit in request["decision_units"]
                    ]
                }
            )
        )


class _FakeClient:
    responses = _FakeResponses()


def test_self_report_runs_the_full_pipeline_on_a_real_fixture_repo(tmp_path: Path) -> None:
    repository = tmp_path / "agentledger"
    repository.mkdir()
    _git(repository, "init")
    _git(repository, "config", "user.name", "Test Author")
    _git(repository, "config", "user.email", "test@example.com")
    (repository / "BUILD_LOG.md").write_text(
        """## Phase 1 — Scaffold
- Built: Created a runnable CLI skeleton.
- Decision made and why: Kept the first phase small.
""",
        encoding="utf-8",
    )
    (repository / "agentledger.py").write_text("VERSION = 1\n", encoding="utf-8")
    _git(repository, "add", ".")
    _commit(repository, "Create Ledger scaffold", "2026-01-01T00:00:00+0000")
    (repository / "agentledger.py").write_text("VERSION = 2\n", encoding="utf-8")
    _git(repository, "add", ".")
    _commit(repository, "Improve Ledger scoring", "2026-01-02T00:00:00+0000")

    terminal_output = StringIO()
    result = run_self_report(
        repository,
        client=_FakeClient(),
        output_path=tmp_path / "self-report.html",
        console=Console(file=terminal_output, force_terminal=False),
    )

    assert result.report_path.exists()
    assert result.commit_count == 2
    assert result.decision_unit_count == 3
    assert "## How we used Codex and GPT-5.6" in result.markdown
    assert "Create Ledger scaffold" in result.markdown
    assert "Improve Ledger scoring" in result.markdown
    assert "Phase 1 — Scaffold" in result.markdown
    assert "AgentLedger audit summary" in terminal_output.getvalue()


def test_self_report_command_emits_readme_ready_markdown(monkeypatch, tmp_path: Path) -> None:
    expected_markdown = "## How we used Codex and GPT-5.6\n\nReal build trail."
    expected_result = SelfReportResult(
        report_path=tmp_path / "self-report.html",
        markdown=expected_markdown,
        decision_unit_count=5,
        commit_count=2,
    )
    monkeypatch.setattr("agentledger.cli.run_self_report", lambda: expected_result)

    result = CliRunner().invoke(app, ["self-report"])

    assert result.exit_code == 0
    assert "Wrote self-audit HTML report" in result.stdout
    assert "README-ready Markdown:" in result.stdout
    assert expected_markdown in result.stdout
