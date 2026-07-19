"""Tests for the HTML and Rich audit report renderers."""

from __future__ import annotations

from dataclasses import asdict
from io import StringIO
import json
from pathlib import Path

from rich.console import Console
from typer.testing import CliRunner

from agentledger.cli import app
from agentledger.report import render_html_report, render_terminal_summary, write_html_report
from agentledger.scan import DecisionUnit
from agentledger.score import FlaggedHunk, RiskScore, TrustScore


def _report_data() -> tuple[list[DecisionUnit], list[RiskScore], list[TrustScore]]:
    units = [
        DecisionUnit(
            commit_sha="high-commit",
            file_path="src/auth/session.py",
            diff_hunk="@@ -1 +1 @@\n-token = old\n+token = renewed\n",
            commit_message="Harden session validation",
            author="Test Author",
            timestamp="2026-01-01T00:00:00Z",
            rationale="Prevent expired sessions from being accepted.",
            rationale_source="gpt-5.6-inferred",
        ),
        DecisionUnit(
            commit_sha="low-commit",
            file_path="docs/guide.md",
            diff_hunk="@@ -1 +1 @@\n-old docs\n+clearer docs\n",
            commit_message="Clarify setup guide",
            author="Test Author",
            timestamp="2026-01-02T00:00:00Z",
            rationale="Explain the local setup sequence.",
            rationale_source="commit_message",
        ),
    ]
    risks = [
        RiskScore("src/auth/session.py", 0.9, 0.02, True, 0.69),
        RiskScore("docs/guide.md", 0.2, 0.02, False, 0.135),
    ]
    trusts = [
        TrustScore(
            "high-commit",
            0.31,
            [FlaggedHunk("src/auth/session.py", "risk score 0.690; matches incident history")],
            "Commit high-commit has 1 high-risk changed file(s) that require careful review.",
        ),
        TrustScore("low-commit", 0.865, [], "Commit low-commit has no high-risk changed files."),
    ]
    return units, risks, trusts


def test_html_report_is_self_contained_and_distinguishes_risk_levels(tmp_path: Path) -> None:
    units, risks, trusts = _report_data()
    output_path = write_html_report(units, risks, trusts, tmp_path / "audit.html")
    report_html = output_path.read_text(encoding="utf-8")

    assert output_path.exists()
    assert "<style>" in report_html
    assert "risk-card risk-high" in report_html
    assert "risk-card risk-low" in report_html
    assert "HIGH RISK · 69%" in report_html
    assert "LOW RISK · 14%" in report_html
    assert "https://" not in report_html
    assert "<link" not in report_html


def test_terminal_summary_shows_high_and_low_risk_sections() -> None:
    units, risks, trusts = _report_data()
    output = StringIO()

    render_terminal_summary(units, risks, trusts, console=Console(file=output, width=110, force_terminal=False))

    terminal_output = output.getvalue()
    assert "AgentLedger audit summary" in terminal_output
    assert "HIGH-RISK HUNKS" in terminal_output
    assert "LOW-RISK HUNKS" in terminal_output
    assert "src/auth/session.py" in terminal_output
    assert "docs/guide.md" in terminal_output


def test_report_command_renders_terminal_and_html_output(tmp_path: Path) -> None:
    units, risks, trusts = _report_data()
    output_path = tmp_path / "report.html"
    score_payload = {
        "decision_units": [asdict(unit) for unit in units],
        "risk_scores": [asdict(risk) for risk in risks],
        "trust_scores": [asdict(trust) for trust in trusts],
    }

    result = CliRunner().invoke(
        app,
        ["report", "--out", str(output_path)],
        input=json.dumps(score_payload),
    )

    assert result.exit_code == 0
    assert "AgentLedger audit summary" in result.stdout
    assert f"Wrote HTML report to {output_path}" in result.stdout
    assert "Decision trail report" in output_path.read_text(encoding="utf-8")


def test_global_demo_report_needs_no_json_input_or_openai_key(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    output_path = tmp_path / "demo-report.html"

    result = CliRunner().invoke(app, ["--demo", "report", "--out", str(output_path)])

    assert result.exit_code == 0
    assert "Wrote synthetic demo HTML report" in result.stdout
    report_html = output_path.read_text(encoding="utf-8")
    assert "src/auth/session.py" in report_html
    assert "risk-card risk-high" in report_html
    assert "risk-card risk-low" in report_html
