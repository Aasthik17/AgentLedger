"""Command-line interface for AgentLedger."""

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence

import typer

from agentledger.demo import demo_decision_units_json, load_demo_decision_units, score_demo_decision_units
from agentledger.enrich import EnrichmentError, enrich_decision_units
from agentledger.report import render_terminal_summary, write_html_report
from agentledger.scan import DecisionUnit, GitScanError, scan_repository
from agentledger.score import FlaggedHunk, RiskScore, ScoreConfigError, TrustScore, score_decision_units

app = typer.Typer(
    name="ledger",
    help="Audit AI-agent-written code changes before merge.",
    no_args_is_help=True,
)


@app.callback()
def application_options(
    ctx: typer.Context,
    demo: bool = typer.Option(
        False,
        "--demo",
        help="Run a bundled synthetic audit without Git or an OpenAI API key.",
    ),
) -> None:
    """Configure options shared by Ledger commands."""
    ctx.ensure_object(dict)
    ctx.obj["demo"] = demo


def _not_implemented() -> None:
    """Keep Phase 1 commands runnable while later pipeline phases are built."""
    typer.echo("not implemented")


def _demo_enabled(ctx: typer.Context, command_demo: bool) -> bool:
    """Support both `ledger --demo report` and `ledger report --demo`."""
    return command_demo or bool(ctx.obj and ctx.obj.get("demo"))


class SelfReportError(RuntimeError):
    """Raised when the project's own build trail cannot be summarized."""


@dataclass(frozen=True)
class SelfReportResult:
    """Artifacts produced by one complete audit of AgentLedger itself."""

    report_path: Path
    markdown: str
    decision_unit_count: int
    commit_count: int


def run_self_report(
    repository: str | Path = ".",
    *,
    client: object | None = None,
    output_path: str | Path | None = None,
    console: object | None = None,
) -> SelfReportResult:
    """Audit this repository from its first commit through the current HEAD."""
    repo_path = Path(repository).resolve()
    decision_units = scan_repository(repo_path)
    enriched_units = enrich_decision_units(decision_units, client=client)
    score_result = score_decision_units(enriched_units, repo_path / ".ledger")
    destination = Path(output_path) if output_path else repo_path / "self-report.html"
    render_terminal_summary(
        score_result.decision_units,
        score_result.risk_scores,
        score_result.trust_scores,
        console=console,
    )
    report_path = write_html_report(
        score_result.decision_units,
        score_result.risk_scores,
        score_result.trust_scores,
        destination,
    )
    commit_subjects = _commit_subjects(repo_path)
    return SelfReportResult(
        report_path=report_path,
        markdown=_readme_markdown(
            commit_subjects,
            _build_log_entries(repo_path / "BUILD_LOG.md"),
            len(score_result.decision_units),
        ),
        decision_unit_count=len(score_result.decision_units),
        commit_count=len(commit_subjects),
    )


def _commit_subjects(repository: Path) -> list[tuple[str, str]]:
    try:
        result = subprocess.run(
            ["git", "-C", str(repository), "log", "--reverse", "--format=%h%x09%s"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as error:
        raise SelfReportError("Could not read this repository's commit history.") from error
    return [tuple(line.split("\t", maxsplit=1)) for line in result.stdout.splitlines() if "\t" in line]


def _build_log_entries(build_log_path: Path) -> list[tuple[str, str]]:
    if not build_log_path.exists():
        raise SelfReportError("BUILD_LOG.md is required to generate the Codex usage summary.")

    entries: list[tuple[str, str]] = []
    current_phase: str | None = None
    built_lines: list[str] = []
    collecting_built = False
    for line in build_log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Phase"):
            if current_phase and built_lines:
                entries.append((current_phase, " ".join(built_lines)))
            current_phase = line.removeprefix("## ")
            built_lines = []
            collecting_built = False
        elif line.startswith("- Built:"):
            built_lines = [line.removeprefix("- Built:").strip()]
            collecting_built = True
        elif collecting_built and line.startswith("- "):
            collecting_built = False
        elif collecting_built and line.strip():
            built_lines.append(line.strip())
    if current_phase and built_lines:
        entries.append((current_phase, " ".join(built_lines)))
    return entries


def _readme_markdown(
    commit_subjects: Sequence[tuple[str, str]],
    build_log_entries: Sequence[tuple[str, str]],
    decision_unit_count: int,
) -> str:
    commit_lines = "\n".join(f"- `{sha}` — {subject}" for sha, subject in commit_subjects)
    build_lines = "\n".join(
        f"- **{phase}:** {built}" for phase, built in build_log_entries if built
    )
    return f"""## How we used Codex and GPT-5.6

AgentLedger was built as a staged, reviewable workflow with Codex. This
self-report audited {decision_unit_count} real per-file decisions from the
project's own committed history, rather than relying on a fabricated demo.

### Real build trail

{commit_lines}

### Codex workflow and engineering decisions

{build_lines}

The human set the product scope, fixed stack, phase order, and review gates in
`AGENTS.md`. Codex implemented each approved phase, ran its deterministic test
suite, documented the decision in `BUILD_LOG.md`, and produced the specific
commit history above. The build log records no overridden product or
architecture decision through these phases.

### GPT-5.6 contribution

`ledger enrich` uses the OpenAI Responses API with strict JSON-schema structured
output to infer a rationale only when a commit message does not clearly explain
why a file changed. It batches several DecisionUnits in each request, preserves
commit-message rationales when they are already clear, and marks inferred
results as `gpt-5.6-inferred`. This self-report then carries those rationales
through deterministic ownership/incident scoring and the final audit report.
"""


@app.command()
def scan(
    ctx: typer.Context,
    path: str | None = typer.Argument(None, help="Repository path to inspect."),
    since: str | None = typer.Option(None, "--since", help="Earliest git ref to include."),
    demo: bool = typer.Option(False, "--demo", help="Use bundled synthetic data instead of Git."),
) -> None:
    """Collect decision units from git history."""
    if _demo_enabled(ctx, demo):
        if since:
            typer.echo("scan failed: --since cannot be combined with --demo.", err=True)
            raise typer.Exit(code=1)
        typer.echo(demo_decision_units_json())
        return
    if path is None:
        typer.echo("scan failed: PATH is required unless --demo is used.", err=True)
        raise typer.Exit(code=1)
    try:
        decision_units = scan_repository(path, since=since)
    except GitScanError as error:
        typer.echo(f"scan failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(json.dumps([asdict(unit) for unit in decision_units], indent=2))


@app.command()
def enrich(
    ctx: typer.Context,
    demo: bool = typer.Option(False, "--demo", help="Use bundled synthetic data without an API call."),
) -> None:
    """Infer missing change rationales with GPT-5.6 from JSON stdin."""
    if _demo_enabled(ctx, demo):
        typer.echo(demo_decision_units_json())
        return
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
    ctx: typer.Context,
    demo: bool = typer.Option(False, "--demo", help="Score bundled synthetic data instead of stdin."),
) -> None:
    """Calculate risk and trust scores from DecisionUnit JSON on stdin."""
    if _demo_enabled(ctx, demo):
        typer.echo(json.dumps(asdict(score_demo_decision_units()), indent=2))
        return
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
    ctx: typer.Context,
    out: str = typer.Option("report.html", "--out", help="HTML report output path."),
    demo: bool = typer.Option(False, "--demo", help="Render the bundled synthetic audit instead of stdin."),
) -> None:
    """Render terminal and HTML reports from score-command JSON on stdin."""
    if _demo_enabled(ctx, demo):
        result = score_demo_decision_units()
        render_terminal_summary(result.decision_units, result.risk_scores, result.trust_scores)
        output_path = write_html_report(
            result.decision_units, result.risk_scores, result.trust_scores, out
        )
        typer.echo(f"Wrote synthetic demo HTML report to {output_path}")
        return
    try:
        score_payload = json.load(sys.stdin)
        decision_units = [DecisionUnit(**unit) for unit in score_payload["decision_units"]]
        risk_scores = [RiskScore(**score) for score in score_payload["risk_scores"]]
        trust_scores = [
            TrustScore(
                commit_sha=score["commit_sha"],
                overall_score=score["overall_score"],
                flagged_hunks=[FlaggedHunk(**flag) for flag in score["flagged_hunks"]],
                summary=score["summary"],
            )
            for score in score_payload["trust_scores"]
        ]
        render_terminal_summary(decision_units, risk_scores, trust_scores)
        output_path = write_html_report(decision_units, risk_scores, trust_scores, out)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
        typer.echo(f"report failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Wrote HTML report to {output_path}")


@app.command(name="self-report")
def self_report(
    ctx: typer.Context,
    demo: bool = typer.Option(False, "--demo", help="Render synthetic data; does not audit this repository."),
) -> None:
    """Run the complete pipeline against AgentLedger's own history."""
    if _demo_enabled(ctx, demo):
        result = score_demo_decision_units()
        render_terminal_summary(result.decision_units, result.risk_scores, result.trust_scores)
        output_path = write_html_report(
            result.decision_units, result.risk_scores, result.trust_scores, "demo-self-report.html"
        )
        typer.echo(f"Wrote synthetic demo HTML report to {output_path}")
        typer.echo("Demo mode does not emit self-report provenance Markdown.")
        return
    try:
        result = run_self_report()
    except (GitScanError, EnrichmentError, ScoreConfigError, SelfReportError, ValueError) as error:
        typer.echo(f"self-report failed: {error}", err=True)
        raise typer.Exit(code=1) from error

    typer.echo(f"Wrote self-audit HTML report to {result.report_path}")
    typer.echo("\nREADME-ready Markdown:\n")
    typer.echo(result.markdown)


def main() -> None:
    """Run the Ledger CLI."""
    app()


if __name__ == "__main__":
    main()
