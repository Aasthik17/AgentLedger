"""Smoke tests for the user-facing CLI documentation."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from agentledger.cli import app


@pytest.mark.parametrize("command", ["scan", "enrich", "score", "report", "self-report"])
def test_each_subcommand_has_help(command: str) -> None:
    result = CliRunner().invoke(app, [command, "--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.stdout
    assert "--help" in result.stdout


def test_root_help_documents_global_demo_option() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "--demo" in result.stdout
    assert "synthetic audit" in result.stdout
