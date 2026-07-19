"""Command-line interface for AgentLedger."""

from dataclasses import asdict
import json
import sys

import typer

from agentledger.enrich import EnrichmentError, enrich_decision_units
from agentledger.scan import DecisionUnit, GitScanError, scan_repository
from agentledger.score import ScoreConfigError, score_decision_units

app = typer.Typer(
    name="ledger",
    help="Audit AI-agent-written code changes before merge.",
    no_args_is_help=True,
)


def _not_implemented() -> None:
    """Keep Phase 1 commands runnable while later pipeline phases are built."""
    typer.echo("not implemented")


@app.command()
def scan(
    path: str = typer.Argument(..., help="Repository path to inspect."),
    since: str | None = typer.Option(None, "--since", help="Earliest git ref to include."),
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Collect decision units from git history."""
    del demo
    try:
        decision_units = scan_repository(path, since=since)
    except GitScanError as error:
        typer.echo(f"scan failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(json.dumps([asdict(unit) for unit in decision_units], indent=2))


@app.command()
def enrich(
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Infer missing change rationales with GPT-5.6 from JSON stdin."""
    del demo
    try:
        serialized_units = json.load(sys.stdin)
        decision_units = [DecisionUnit(**unit) for unit in serialized_units]
        enriched_units = enrich_decision_units(decision_units)
    except (json.JSONDecodeError, TypeError, EnrichmentError) as error:
        typer.echo(f"enrich failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(json.dumps([asdict(unit) for unit in enriched_units], indent=2))


@app.command()
def score(
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Calculate risk and trust scores from DecisionUnit JSON on stdin."""
    del demo
    try:
        serialized_units = json.load(sys.stdin)
        decision_units = [DecisionUnit(**unit) for unit in serialized_units]
        score_result = score_decision_units(decision_units)
    except (json.JSONDecodeError, TypeError, ScoreConfigError) as error:
        typer.echo(f"score failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(json.dumps(asdict(score_result), indent=2))


@app.command()
def report(
    out: str = typer.Option("report.html", "--out", help="HTML report output path."),
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Render the terminal and HTML audit report."""
    del out, demo
    _not_implemented()


@app.command(name="self-report")
def self_report(
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Run the complete pipeline against AgentLedger's own history."""
    del demo
    _not_implemented()


def main() -> None:
    """Run the Ledger CLI."""
    app()


if __name__ == "__main__":
    main()
