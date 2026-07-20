"""Unit tests for batched GPT-5.6 rationale enrichment."""

from __future__ import annotations

from dataclasses import asdict
import json
from types import SimpleNamespace

import httpx
import pytest
from typer.testing import CliRunner

from agentledger.cli import app
from agentledger import enrich
from agentledger.enrich import EnrichmentError, enrich_decision_units
from agentledger.scan import DecisionUnit


def _unit(commit_message: str, *, file_path: str = "src/service.py") -> DecisionUnit:
    return DecisionUnit(
        commit_sha="abc123",
        file_path=file_path,
        diff_hunk="@@ -1 +1 @@\n-old\n+new\n",
        commit_message=commit_message,
        author="Test Author",
        timestamp="2026-01-01T00:00:00Z",
        rationale=None,
        rationale_source="commit_message",
    )


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.calls.append(kwargs)
        request = json.loads(kwargs["input"][1]["content"])
        rationales = [
            {
                "unit_id": unit["unit_id"],
                "rationale": f"Inferred rationale for {unit['file_path']}.",
            }
            for unit in request["decision_units"]
        ]
        return SimpleNamespace(output_text=json.dumps({"rationales": rationales}))


class FakeClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


def test_enrich_batches_unclear_units_and_preserves_clear_commit_rationales() -> None:
    units = [
        _unit("Update request handling", file_path="src/requests.py"),
        _unit(
            "Harden request validation\n\nReject empty payloads before processing requests.",
            file_path="src/validation.py",
        ),
        _unit("Refactor worker", file_path="src/worker.py"),
        _unit("Fix bug", file_path="src/session.py"),
    ]
    client = FakeClient()

    enriched = enrich_decision_units(units, client=client, batch_size=2)

    assert len(client.responses.calls) == 2
    assert enriched[0].rationale == "Inferred rationale for src/requests.py."
    assert enriched[0].rationale_source == "gpt-5.6-inferred"
    assert enriched[1].rationale == "Reject empty payloads before processing requests."
    assert enriched[1].rationale_source == "commit_message"
    assert enriched[2].rationale_source == "gpt-5.6-inferred"
    assert enriched[3].rationale_source == "gpt-5.6-inferred"

    first_request = client.responses.calls[0]
    assert first_request["model"] == "gpt-5.6"
    assert first_request["max_output_tokens"] == 512
    assert first_request["text"]["format"]["type"] == "json_schema"
    assert first_request["text"]["format"]["strict"] is True


def test_enrich_is_idempotent_for_existing_rationales() -> None:
    existing = DecisionUnit(
        **{
            **asdict(_unit("Fix bug")),
            "rationale": "A prior enrichment result.",
            "rationale_source": "gpt-5.6-inferred",
        }
    )
    client = FakeClient()

    assert enrich_decision_units([existing], client=client) == [existing]
    assert client.responses.calls == []


def test_enrich_rejects_incomplete_structured_output() -> None:
    class IncompleteResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            del kwargs
            return SimpleNamespace(output_text='{"rationales": []}')

    client = SimpleNamespace(responses=IncompleteResponses())

    with pytest.raises(EnrichmentError, match="exactly one rationale"):
        enrich_decision_units([_unit("Fix bug")], client=client)


def test_enrich_wraps_provider_errors_without_exposing_a_traceback() -> None:
    class CreditLimitedResponses:
        def create(self, **kwargs: object) -> SimpleNamespace:
            del kwargs
            request = httpx.Request("POST", "https://provider.example/responses")
            response = httpx.Response(402, request=request)
            from openai import APIStatusError

            raise APIStatusError("credit limit reached", response=response, body={})

    client = SimpleNamespace(responses=CreditLimitedResponses())

    with pytest.raises(EnrichmentError, match="GPT-5.6 enrichment request failed: credit limit"):
        enrich_decision_units([_unit("Fix bug")], client=client)


def test_enrich_command_reads_and_writes_decision_unit_json() -> None:
    unit = _unit("A clear change because it rejects invalid requests")

    result = CliRunner().invoke(app, ["enrich"], input=json.dumps([asdict(unit)]))

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["rationale"] == "A clear change because it rejects invalid requests"
    assert payload[0]["rationale_source"] == "commit_message"


def test_enrich_explains_when_openai_key_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["enrich"], input=json.dumps([asdict(_unit("Fix bug"))]))

    assert result.exit_code == 1
    assert "Set OPENAI_API_KEY or OPENROUTER_API_KEY" in result.stdout
    assert "Traceback" not in result.stdout


def test_demo_enrich_never_requires_an_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = CliRunner().invoke(app, ["enrich", "--demo"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert all(unit["rationale"] for unit in payload)


def test_enrich_uses_openrouter_gpt_5_6_without_storing_a_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    class OpenRouterClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)
            self.responses = FakeResponses()
            captured["responses"] = self.responses

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")
    monkeypatch.setattr(enrich, "OpenAI", OpenRouterClient)

    enriched = enrich_decision_units([_unit("Fix bug")])

    assert captured["api_key"] == "test-openrouter-key"
    assert captured["base_url"] == "https://openrouter.ai/api/v1"
    responses = captured["responses"]
    assert isinstance(responses, FakeResponses)
    assert responses.calls[0]["model"] == "openai/gpt-5.6-sol"
    assert enriched[0].rationale_source == "gpt-5.6-inferred"
