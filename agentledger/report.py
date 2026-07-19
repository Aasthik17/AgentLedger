"""Terminal and self-contained HTML report rendering for AgentLedger."""

from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Sequence

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agentledger.scan import DecisionUnit
from agentledger.score import FLAGGED_RISK_THRESHOLD, RiskScore, TrustScore


def write_html_report(
    decision_units: Sequence[DecisionUnit],
    risk_scores: Sequence[RiskScore],
    trust_scores: Sequence[TrustScore],
    output_path: str | Path,
) -> Path:
    """Write a standalone audit report with no external assets or CDN links."""
    destination = Path(output_path)
    destination.write_text(
        render_html_report(decision_units, risk_scores, trust_scores), encoding="utf-8"
    )
    return destination


def render_html_report(
    decision_units: Sequence[DecisionUnit],
    risk_scores: Sequence[RiskScore],
    trust_scores: Sequence[TrustScore],
) -> str:
    """Render the decision trail, flagged hunks, and trust scores as HTML."""
    _validate_report_inputs(decision_units, risk_scores)
    commits = _commit_groups(decision_units, risk_scores)
    trust_by_commit = {trust_score.commit_sha: trust_score for trust_score in trust_scores}
    flagged_count = sum(len(trust_score.flagged_hunks) for trust_score in trust_scores)
    commit_sections = "".join(
        _commit_html(commit_sha, unit_scores, trust_by_commit.get(commit_sha))
        for commit_sha, unit_scores in commits.items()
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AgentLedger audit report</title>
<style>
:root {{ color-scheme: dark; --bg: #101727; --surface: #18243a; --muted: #9fb0c8; --text: #eff6ff; --line: #2c3d5b; --high: #ff715b; --high-bg: #3a2027; --low: #42d3a4; --low-bg: #16372f; --medium: #f5be55; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; background: var(--bg); color: var(--text); font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; line-height: 1.5; }}
main {{ max-width: 1200px; margin: 0 auto; padding: 44px 24px 80px; }}
header {{ display: flex; justify-content: space-between; align-items: end; gap: 24px; border-bottom: 1px solid var(--line); padding-bottom: 28px; margin-bottom: 28px; }}
h1 {{ font-size: clamp(2rem, 4vw, 3.5rem); letter-spacing: -0.04em; margin: 0; }}
h2 {{ margin: 0; font-size: 1.25rem; }}
p {{ margin: 8px 0 0; }}
.eyebrow {{ color: var(--low); font-size: 0.78rem; font-weight: 800; letter-spacing: 0.14em; text-transform: uppercase; }}
.muted {{ color: var(--muted); }}
.metrics {{ display: grid; grid-template-columns: repeat(3, minmax(110px, 1fr)); gap: 12px; min-width: 360px; }}
.metric {{ background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 16px; }}
.metric strong {{ display: block; font-size: 1.5rem; }}
.commit {{ border: 1px solid var(--line); background: var(--surface); border-radius: 16px; margin: 22px 0; overflow: hidden; }}
.commit-head {{ display: flex; justify-content: space-between; gap: 18px; padding: 22px; border-bottom: 1px solid var(--line); }}
.sha {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: var(--muted); font-size: 0.82rem; }}
.trust {{ font-weight: 800; font-size: 1.6rem; text-align: right; white-space: nowrap; }}
.flagged {{ border-left: 4px solid var(--high); background: var(--high-bg); color: #ffd6d0; padding: 12px 16px; margin: 16px 22px 0; border-radius: 6px; }}
.trail {{ padding: 12px 22px 22px; display: grid; gap: 14px; }}
.risk-card {{ border: 1px solid var(--line); border-left-width: 6px; border-radius: 10px; padding: 16px; }}
.risk-high {{ border-left-color: var(--high); background: var(--high-bg); }}
.risk-low {{ border-left-color: var(--low); background: var(--low-bg); }}
.risk-medium {{ border-left-color: var(--medium); background: #382e17; }}
.file-row {{ display: flex; justify-content: space-between; gap: 16px; align-items: baseline; }}
.file-row code {{ font-size: 1rem; font-weight: 750; overflow-wrap: anywhere; }}
.badge {{ border-radius: 999px; font-size: 0.75rem; font-weight: 800; letter-spacing: 0.06em; padding: 4px 9px; white-space: nowrap; }}
.badge-high {{ background: var(--high); color: #281215; }} .badge-low {{ background: var(--low); color: #09251e; }} .badge-medium {{ background: var(--medium); color: #302407; }}
.details {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; color: var(--muted); font-size: 0.86rem; margin-top: 10px; }}
.rationale {{ margin-top: 12px; }}
pre {{ overflow-x: auto; white-space: pre; background: #0b1220; border: 1px solid #24324b; border-radius: 8px; padding: 13px; margin: 14px 0 0; color: #dce8fa; font-size: 0.78rem; line-height: 1.45; }}
@media (max-width: 720px) {{ header, .commit-head {{ display: block; }} .metrics {{ min-width: 0; margin-top: 18px; }} .trust {{ text-align: left; margin-top: 12px; }} .details {{ grid-template-columns: 1fr; }} }}
</style>
</head>
<body><main>
<header>
  <div><div class="eyebrow">AgentLedger · AI change audit</div><h1>Decision trail report</h1><p class="muted">Review AI-assisted commits with provenance, rationale, and risk in one place.</p></div>
  <div class="metrics"><div class="metric"><strong>{len(commits)}</strong><span class="muted">commits</span></div><div class="metric"><strong>{len(decision_units)}</strong><span class="muted">file decisions</span></div><div class="metric"><strong>{flagged_count}</strong><span class="muted">flagged hunks</span></div></div>
</header>
{commit_sections}
</main></body></html>"""


def render_terminal_summary(
    decision_units: Sequence[DecisionUnit],
    risk_scores: Sequence[RiskScore],
    trust_scores: Sequence[TrustScore],
    console: Console | None = None,
) -> None:
    """Render the same audit conclusions as a camera-readable Rich summary."""
    _validate_report_inputs(decision_units, risk_scores)
    report_console = console or Console()
    trust_by_commit = {trust_score.commit_sha: trust_score for trust_score in trust_scores}
    commits = _commit_groups(decision_units, risk_scores)

    report_console.print(Panel.fit("[bold cyan]AgentLedger audit summary[/bold cyan]", border_style="cyan"))
    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Commit", style="dim", no_wrap=True)
    table.add_column("Trust", justify="right")
    table.add_column("Flagged", justify="center")
    table.add_column("Review summary")
    for commit_sha, unit_scores in commits.items():
        trust = trust_by_commit.get(commit_sha)
        if trust is None:
            continue
        trust_style = "green" if trust.overall_score >= 0.7 else "yellow" if trust.overall_score >= 0.4 else "red"
        table.add_row(
            commit_sha[:12],
            Text(f"{trust.overall_score:.0%}", style=f"bold {trust_style}"),
            str(len(trust.flagged_hunks)),
            trust.summary,
        )
    report_console.print(table)

    high_risk = [(unit, score) for unit, score in zip(decision_units, risk_scores, strict=True) if score.risk_score >= FLAGGED_RISK_THRESHOLD]
    low_risk = [(unit, score) for unit, score in zip(decision_units, risk_scores, strict=True) if score.risk_score < FLAGGED_RISK_THRESHOLD]
    if high_risk:
        report_console.print(
            Panel(
                "\n".join(f"[bold red]{unit.file_path}[/bold red] — {score.risk_score:.0%} risk" for unit, score in high_risk),
                title="HIGH-RISK HUNKS — review before merge",
                border_style="red",
            )
        )
    if low_risk:
        report_console.print(
            Panel(
                "\n".join(f"[bold green]{unit.file_path}[/bold green] — {score.risk_score:.0%} risk" for unit, score in low_risk),
                title="LOW-RISK HUNKS",
                border_style="green",
            )
        )


def _commit_groups(
    decision_units: Sequence[DecisionUnit], risk_scores: Sequence[RiskScore]
) -> dict[str, list[tuple[DecisionUnit, RiskScore]]]:
    groups: dict[str, list[tuple[DecisionUnit, RiskScore]]] = defaultdict(list)
    for unit, score in zip(decision_units, risk_scores, strict=True):
        groups[unit.commit_sha].append((unit, score))
    return groups


def _commit_html(
    commit_sha: str,
    unit_scores: list[tuple[DecisionUnit, RiskScore]],
    trust_score: TrustScore | None,
) -> str:
    trust_value = trust_score.overall_score if trust_score else 0.0
    summary = trust_score.summary if trust_score else "No trust score was produced for this commit."
    flags = "".join(
        f"<div class=\"flagged\"><strong>Review {escape(flag.file_path)}</strong> — {escape(flag.reason)}</div>"
        for flag in (trust_score.flagged_hunks if trust_score else [])
    )
    cards = "".join(_decision_unit_html(unit, score) for unit, score in unit_scores)
    return f"""<section class="commit">
<div class="commit-head"><div><h2>{escape(unit_scores[0][0].commit_message.splitlines()[0])}</h2><div class="sha">{escape(commit_sha)}</div><p class="muted">{escape(summary)}</p></div><div class="trust">{trust_value:.0%}<div class="muted" style="font-size:.78rem">TRUST SCORE</div></div></div>
{flags}<div class="trail">{cards}</div></section>"""


def _decision_unit_html(unit: DecisionUnit, score: RiskScore) -> str:
    risk_class, badge = _risk_presentation(score.risk_score)
    incident_text = "incident history match" if score.incident_history_hit else "no incident match"
    rationale = unit.rationale or "Rationale has not been enriched."
    return f"""<article class="risk-card {risk_class}">
<div class="file-row"><code>{escape(unit.file_path)}</code><span class="badge badge-{badge}">{badge.upper()} RISK · {score.risk_score:.0%}</span></div>
<div class="details"><span>Criticality: {score.criticality:.0%}</span><span>Change size: {score.change_size_factor:.0%}</span><span>{incident_text}</span></div>
<p class="rationale"><strong>Why:</strong> {escape(rationale)} <span class="muted">({escape(unit.rationale_source)})</span></p>
<pre>{escape(unit.diff_hunk)}</pre>
</article>"""


def _risk_presentation(risk_score: float) -> tuple[str, str]:
    if risk_score >= FLAGGED_RISK_THRESHOLD:
        return "risk-high", "high"
    if risk_score <= 0.3:
        return "risk-low", "low"
    return "risk-medium", "medium"


def _validate_report_inputs(
    decision_units: Sequence[DecisionUnit], risk_scores: Sequence[RiskScore]
) -> None:
    if len(decision_units) != len(risk_scores):
        raise ValueError("Each decision unit must have exactly one risk score.")
    for unit, risk_score in zip(decision_units, risk_scores, strict=True):
        if unit.file_path != risk_score.file_path:
            raise ValueError("Decision units and risk scores must be aligned by file path.")
