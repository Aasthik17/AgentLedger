"""Phase 1 wiring check for the test suite."""

from typer.testing import CliRunner

from agentledger.cli import app


def test_scan_stub_is_runnable() -> None:
    result = CliRunner().invoke(app, ["scan", "."])

    assert result.exit_code == 0
    assert result.stdout == "not implemented\n"
