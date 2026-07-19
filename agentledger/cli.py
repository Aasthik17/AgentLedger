"""Command-line interface for AgentLedger."""

from dataclasses import asdict
import json

import typer

from agentledger.scan import GitScanError, scan_repository

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
    """Infer missing change rationales with GPT-5.6."""
    del demo
    _not_implemented()


@app.command()
def score(
    demo: bool = typer.Option(False, "--demo", help="Use bundled sample data."),
) -> None:
    """Calculate per-change risk and commit trust scores."""
    del demo
    _not_implemented()


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
