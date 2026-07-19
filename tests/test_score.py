"""Deterministic tests for ownership and incident-history scoring."""

from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentledger.cli import app
from agentledger.scan import DecisionUnit
from agentledger.score import ScoreConfigError, score_decision_units


@pytest.fixture()
def ledger_config(tmp_path: Path) -> Path:
    ledger_directory = tmp_path / ".ledger"
    ledger_directory.mkdir()
    (ledger_directory / "ownership.yaml").write_text(
        """paths:
  \"src/auth/**\": { owner: \"security-team\", criticality: high }
  \"docs/**\": { owner: \"any\", criticality: low }
  \"**\": { owner: \"unassigned\", criticality: medium }
""",
        encoding="utf-8",
    )
    (ledger_directory / "incidents.json").write_text(
        json.dumps(
            [
                {
                    "id": "INC-001",
                    "files": ["src/auth/session.py"],
                    "summary": "session token not invalidated on logout",
                    "date": "2025-11-02",
                }
            ]
        ),
        encoding="utf-8",
    )
    return ledger_directory


def _unit(file_path: str, diff_hunk: str, commit_sha: str = "commit-one") -> DecisionUnit:
    return DecisionUnit(
        commit_sha=commit_sha,
        file_path=file_path,
        diff_hunk=diff_hunk,
        commit_message="Change test fixture",
        author="Test Author",
        timestamp="2026-01-01T00:00:00Z",
        rationale="Test rationale",
        rationale_source="commit_message",
    )


def test_score_uses_ownership_incidents_and_change_size(ledger_config: Path) -> None:
    decision_units = [
        _unit("src/auth/session.py", "@@ -1 +1,2 @@\n-old\n+new\n+extra\n"),
        _unit("docs/guide.md", "@@ -1 +1 @@\n-old\n+new\n"),
    ]

    result = score_decision_units(decision_units, ledger_config)

    assert result.risk_scores[0].criticality == 0.9
    assert result.risk_scores[0].change_size_factor == 0.03
    assert result.risk_scores[0].incident_history_hit is True
    assert result.risk_scores[0].risk_score == 0.693
    assert result.risk_scores[1].criticality == 0.2
    assert result.risk_scores[1].change_size_factor == 0.02
    assert result.risk_scores[1].incident_history_hit is False
    assert result.risk_scores[1].risk_score == 0.135

    trust_score = result.trust_scores[0]
    assert trust_score.commit_sha == "commit-one"
    assert trust_score.overall_score == 0.586
    assert trust_score.flagged_hunks[0].file_path == "src/auth/session.py"
    assert "matches incident history" in trust_score.flagged_hunks[0].reason


def test_score_rolls_up_each_commit_independently(ledger_config: Path) -> None:
    result = score_decision_units(
        [
            _unit("docs/guide.md", "@@ -1 +1 @@\n-old\n+new\n", commit_sha="low-risk"),
            _unit("src/auth/session.py", "@@ -1 +1 @@\n-old\n+new\n", commit_sha="high-risk"),
        ],
        ledger_config,
    )

    trust_by_commit = {trust_score.commit_sha: trust_score for trust_score in result.trust_scores}
    assert trust_by_commit["low-risk"].overall_score == 0.865
    assert trust_by_commit["low-risk"].flagged_hunks == []
    assert trust_by_commit["high-risk"].overall_score == 0.31
    assert trust_by_commit["high-risk"].flagged_hunks[0].file_path == "src/auth/session.py"


def test_score_requires_a_matching_ownership_rule(tmp_path: Path) -> None:
    ledger_directory = tmp_path / ".ledger"
    ledger_directory.mkdir()
    (ledger_directory / "ownership.yaml").write_text(
        "paths:\n  \"docs/**\": { owner: \"any\", criticality: low }\n",
        encoding="utf-8",
    )
    (ledger_directory / "incidents.json").write_text("[]", encoding="utf-8")

    with pytest.raises(ScoreConfigError, match="No ownership rule"):
        score_decision_units([_unit("src/app.py", "@@ -1 +1 @@\n-old\n+new\n")], ledger_directory)


def test_score_uses_spec_default_when_ledger_files_do_not_exist(tmp_path: Path) -> None:
    result = score_decision_units(
        [_unit("src/app.py", "@@ -1 +1 @@\n-old\n+new\n")],
        tmp_path / "missing-ledger",
    )

    assert result.risk_scores[0].criticality == 0.5
    assert result.risk_scores[0].risk_score == 0.33
    assert result.trust_scores[0].overall_score == 0.67


def test_score_command_reads_and_writes_json(ledger_config: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ledger_config.parent)
    unit = _unit("docs/guide.md", "@@ -1 +1 @@\n-old\n+new\n")

    result = CliRunner().invoke(app, ["score"], input=json.dumps([asdict(unit)]))

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["risk_scores"][0]["risk_score"] == 0.135
    assert payload["trust_scores"][0]["overall_score"] == 0.865
