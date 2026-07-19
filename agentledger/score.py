"""Ownership and incident-history risk scoring for AgentLedger."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
from typing import Any, Sequence

import yaml

from agentledger.scan import DecisionUnit


CRITICALITY_VALUES = {"low": 0.2, "medium": 0.5, "high": 0.9}
INCIDENT_CRITICALITY_FLOOR = 0.75
CHANGE_SIZE_LINE_CAP = 100
FLAGGED_RISK_THRESHOLD = 0.6


class ScoreConfigError(ValueError):
    """Raised when Ledger's ownership or incident configuration is invalid."""


@dataclass(frozen=True)
class RiskScore:
    """Risk assessment for one changed file, matching the project specification."""

    file_path: str
    criticality: float
    change_size_factor: float
    incident_history_hit: bool
    risk_score: float


@dataclass(frozen=True)
class FlaggedHunk:
    """A file that needs a careful reviewer pass."""

    file_path: str
    reason: str


@dataclass(frozen=True)
class TrustScore:
    """Trust assessment for one commit, matching the project specification."""

    commit_sha: str
    overall_score: float
    flagged_hunks: list[FlaggedHunk]
    summary: str


@dataclass(frozen=True)
class ScoreResult:
    """The per-file and per-commit outputs of one scoring pass."""

    risk_scores: list[RiskScore]
    trust_scores: list[TrustScore]


@dataclass(frozen=True)
class OwnershipRule:
    """A normalized ownership path rule."""

    pattern: str
    criticality: float


def load_ledger_config(ledger_directory: str | Path = ".ledger") -> tuple[list[OwnershipRule], set[str]]:
    """Load Ledger config, using the SPEC defaults until Phase 7 supplies data."""
    ledger_path = Path(ledger_directory)
    ownership_path = ledger_path / "ownership.yaml"
    incidents_path = ledger_path / "incidents.json"

    ownership_data: dict[str, Any]
    if ownership_path.exists():
        with ownership_path.open(encoding="utf-8") as ownership_file:
            ownership_data = yaml.safe_load(ownership_file) or {}
    else:
        ownership_data = {"paths": {"**": {"owner": "unassigned", "criticality": "medium"}}}

    incidents_data: list[dict[str, Any]]
    if incidents_path.exists():
        with incidents_path.open(encoding="utf-8") as incidents_file:
            incidents_data = json.load(incidents_file)
    else:
        incidents_data = []

    return _parse_ownership_rules(ownership_data), _incident_file_paths(incidents_data)


def score_decision_units(
    decision_units: Sequence[DecisionUnit], ledger_directory: str | Path = ".ledger"
) -> ScoreResult:
    """Calculate deterministic per-file risks and per-commit trust scores."""
    ownership_rules, incident_files = load_ledger_config(ledger_directory)
    risk_scores = [
        _risk_score_for_unit(unit, ownership_rules, incident_files) for unit in decision_units
    ]
    return ScoreResult(
        risk_scores=risk_scores,
        trust_scores=_trust_scores_for_commits(decision_units, risk_scores),
    )


def _parse_ownership_rules(ownership_data: dict[str, Any]) -> list[OwnershipRule]:
    paths = ownership_data.get("paths")
    if not isinstance(paths, dict) or not paths:
        raise ScoreConfigError("ownership.yaml must contain a non-empty paths mapping.")

    rules: list[OwnershipRule] = []
    for pattern, details in paths.items():
        if not isinstance(pattern, str) or not isinstance(details, dict):
            raise ScoreConfigError("Each ownership path must map to a configuration object.")
        criticality_name = details.get("criticality")
        if criticality_name not in CRITICALITY_VALUES:
            raise ScoreConfigError(
                f"Ownership path {pattern!r} must use low, medium, or high criticality."
            )
        rules.append(OwnershipRule(pattern=pattern, criticality=CRITICALITY_VALUES[criticality_name]))
    return rules


def _incident_file_paths(incidents_data: list[dict[str, Any]]) -> set[str]:
    if not isinstance(incidents_data, list):
        raise ScoreConfigError("incidents.json must contain a JSON array.")

    incident_files: set[str] = set()
    for incident in incidents_data:
        if not isinstance(incident, dict) or not isinstance(incident.get("files"), list):
            raise ScoreConfigError("Every incident must contain a files array.")
        incident_files.update(file_path for file_path in incident["files"] if isinstance(file_path, str))
    return incident_files


def _risk_score_for_unit(
    unit: DecisionUnit, ownership_rules: list[OwnershipRule], incident_files: set[str]
) -> RiskScore:
    incident_history_hit = unit.file_path in incident_files
    ownership_criticality = _criticality_for_path(unit.file_path, ownership_rules)
    criticality = max(ownership_criticality, INCIDENT_CRITICALITY_FLOOR) if incident_history_hit else ownership_criticality
    change_size_factor = _change_size_factor(unit.diff_hunk)
    risk_score = round(
        min(1.0, (0.65 * criticality) + (0.25 * change_size_factor) + (0.1 if incident_history_hit else 0.0)),
        3,
    )
    return RiskScore(
        file_path=unit.file_path,
        criticality=criticality,
        change_size_factor=change_size_factor,
        incident_history_hit=incident_history_hit,
        risk_score=risk_score,
    )


def _criticality_for_path(file_path: str, rules: list[OwnershipRule]) -> float:
    matches = [rule for rule in rules if PurePosixPath(file_path).match(rule.pattern)]
    if not matches:
        raise ScoreConfigError(f"No ownership rule matches {file_path!r}; add a ** fallback rule.")
    return max(matches, key=lambda rule: _pattern_specificity(rule.pattern)).criticality


def _pattern_specificity(pattern: str) -> int:
    return len(pattern.replace("*", "").replace("?", ""))


def _change_size_factor(diff_hunk: str) -> float:
    changed_lines = sum(
        1
        for line in diff_hunk.splitlines()
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    )
    return round(min(1.0, changed_lines / CHANGE_SIZE_LINE_CAP), 3)


def _trust_scores_for_commits(
    decision_units: Sequence[DecisionUnit], risk_scores: Sequence[RiskScore]
) -> list[TrustScore]:
    risks_by_commit: dict[str, list[RiskScore]] = defaultdict(list)
    for unit, risk_score in zip(decision_units, risk_scores, strict=True):
        risks_by_commit[unit.commit_sha].append(risk_score)

    return [_trust_score_for_commit(sha, commit_risks) for sha, commit_risks in risks_by_commit.items()]


def _trust_score_for_commit(commit_sha: str, risk_scores: list[RiskScore]) -> TrustScore:
    overall_score = round(1.0 - (sum(score.risk_score for score in risk_scores) / len(risk_scores)), 3)
    flagged_hunks = [
        FlaggedHunk(file_path=score.file_path, reason=_flag_reason(score))
        for score in risk_scores
        if score.risk_score >= FLAGGED_RISK_THRESHOLD
    ]
    if flagged_hunks:
        summary = (
            f"Commit {commit_sha} has {len(flagged_hunks)} high-risk changed file(s) "
            "that require careful review."
        )
    else:
        summary = f"Commit {commit_sha} has no high-risk changed files."
    return TrustScore(
        commit_sha=commit_sha,
        overall_score=overall_score,
        flagged_hunks=flagged_hunks,
        summary=summary,
    )


def _flag_reason(score: RiskScore) -> str:
    details = [f"risk score {score.risk_score:.3f}", f"criticality {score.criticality:.2f}"]
    if score.incident_history_hit:
        details.append("matches incident history")
    return "; ".join(details)
