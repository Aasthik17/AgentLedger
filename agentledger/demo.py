"""Bundled synthetic data for AgentLedger's zero-setup demonstration."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from agentledger.scan import DecisionUnit
from agentledger.score import ScoreResult, score_decision_units


SAMPLE_DATA_DIRECTORY = Path(__file__).resolve().parents[1] / "sample-data"


def load_demo_decision_units() -> list[DecisionUnit]:
    """Load clearly-labelled synthetic decision units without using Git or an API."""
    source = SAMPLE_DATA_DIRECTORY / "decision-units.json"
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(f"Could not load bundled demo data from {source}.") from error
    return [DecisionUnit(**unit) for unit in payload]


def score_demo_decision_units() -> ScoreResult:
    """Score the bundled demo against its synthetic ownership configuration."""
    return score_decision_units(load_demo_decision_units(), SAMPLE_DATA_DIRECTORY)


def demo_decision_units_json() -> str:
    """Serialize demo units for CLI commands that normally stream JSON."""
    return json.dumps([asdict(unit) for unit in load_demo_decision_units()], indent=2)
