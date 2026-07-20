"""GPT-5.6 rationale enrichment for AgentLedger decision units."""

from __future__ import annotations

from dataclasses import replace
import json
import os
from typing import Any, Protocol, Sequence

from openai import APIError, OpenAI

from agentledger.scan import DecisionUnit


MODEL = "gpt-5.6"
OPENROUTER_MODEL = "openai/gpt-5.6-sol"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_BATCH_SIZE = 6
MAX_RATIONALE_OUTPUT_TOKENS = 512


class EnrichmentError(RuntimeError):
    """Raised when an enrichment response cannot be used safely."""


class ResponsesClient(Protocol):
    """The small portion of the OpenAI client used by this module."""

    responses: Any


RATIONALE_BATCH_SCHEMA = {
    "type": "object",
    "properties": {
        "rationales": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "unit_id": {"type": "string"},
                    "rationale": {"type": "string"},
                },
                "required": ["unit_id", "rationale"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["rationales"],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTIONS = """You reconstruct the engineering rationale behind code changes.
For each decision unit, state the likely reason the change was made, based only
on its commit message and patch. Be specific, concise, and do not claim facts
that are not supported by the supplied evidence. Return one rationale for every
unit_id in the requested JSON schema."""


def enrich_decision_units(
    decision_units: Sequence[DecisionUnit],
    *,
    client: ResponsesClient | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[DecisionUnit]:
    """Fill missing rationales, batching unclear commit messages per API request.

    Clear commit-message rationales never use the API. Units with an existing
    rationale are returned unchanged so enrichment remains idempotent.
    """
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")

    enriched = list(decision_units)
    units_to_infer: list[tuple[int, DecisionUnit]] = []

    for index, unit in enumerate(enriched):
        if unit.rationale is not None:
            continue
        if _commit_message_explains_why(unit.commit_message):
            enriched[index] = replace(
                unit,
                rationale=_rationale_from_commit_message(unit.commit_message),
                rationale_source="commit_message",
            )
        else:
            units_to_infer.append((index, unit))

    if not units_to_infer:
        return enriched

    responses_client, model = _responses_client_and_model(client)
    for batch in _batches(units_to_infer, batch_size):
        rationales = _infer_batch(responses_client, batch, model)
        for index, unit in batch:
            enriched[index] = replace(
                unit,
                rationale=rationales[str(index)],
                rationale_source="gpt-5.6-inferred",
            )

    return enriched


def _responses_client_and_model(
    client: ResponsesClient | None,
) -> tuple[ResponsesClient, str]:
    """Select direct OpenAI or the OpenRouter-compatible Responses endpoint."""
    if client is not None:
        return client, MODEL

    openai_key = os.environ.get("OPENAI_API_KEY")
    if openai_key:
        return OpenAI(api_key=openai_key), MODEL

    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if openrouter_key:
        return (
            OpenAI(api_key=openrouter_key, base_url=OPENROUTER_BASE_URL),
            OPENROUTER_MODEL,
        )

    raise EnrichmentError(
        "No API key is set. Set OPENAI_API_KEY or OPENROUTER_API_KEY, or use `--demo`."
    )


def _commit_message_explains_why(message: str) -> bool:
    """Use a conservative local heuristic before spending an API request."""
    paragraphs = [paragraph.strip() for paragraph in message.split("\n\n") if paragraph.strip()]
    if len(paragraphs) > 1 and len(paragraphs[-1]) >= 12:
        return True

    lower_message = " ".join(message.lower().split())
    rationale_markers = (" because ", " so that ", " to prevent ", " to support ", " to avoid ")
    return any(marker in f" {lower_message} " for marker in rationale_markers)


def _rationale_from_commit_message(message: str) -> str:
    paragraphs = [paragraph.strip() for paragraph in message.split("\n\n") if paragraph.strip()]
    return paragraphs[-1]


def _batches(
    items: list[tuple[int, DecisionUnit]], batch_size: int
) -> list[list[tuple[int, DecisionUnit]]]:
    return [items[start : start + batch_size] for start in range(0, len(items), batch_size)]


def _infer_batch(
    client: ResponsesClient, batch: list[tuple[int, DecisionUnit]], model: str
) -> dict[str, str]:
    requested_units = [
        {
            "unit_id": str(index),
            "file_path": unit.file_path,
            "commit_message": unit.commit_message,
            "diff_hunk": unit.diff_hunk,
        }
        for index, unit in batch
    ]
    try:
        response = client.responses.create(
            model=model,
            input=[
                {"role": "system", "content": SYSTEM_INSTRUCTIONS},
                {"role": "user", "content": json.dumps({"decision_units": requested_units})},
            ],
            max_output_tokens=MAX_RATIONALE_OUTPUT_TOKENS,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "decision_unit_rationales",
                    "strict": True,
                    "schema": RATIONALE_BATCH_SCHEMA,
                }
            },
        )
    except APIError as error:
        message = getattr(error, "message", None) or "the provider rejected the request"
        raise EnrichmentError(f"GPT-5.6 enrichment request failed: {message}") from error
    return _parse_rationales(response.output_text, {str(index) for index, _ in batch})


def _parse_rationales(output_text: str, expected_ids: set[str]) -> dict[str, str]:
    try:
        payload = json.loads(output_text)
        entries = payload["rationales"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise EnrichmentError("GPT-5.6 returned an invalid rationale payload.") from error

    if not isinstance(entries, list):
        raise EnrichmentError("GPT-5.6 returned rationales in an invalid format.")

    rationales: dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise EnrichmentError("GPT-5.6 returned an invalid rationale entry.")
        unit_id = entry.get("unit_id")
        rationale = entry.get("rationale")
        if not isinstance(unit_id, str) or not isinstance(rationale, str) or not rationale.strip():
            raise EnrichmentError("GPT-5.6 returned an incomplete rationale entry.")
        if unit_id in rationales:
            raise EnrichmentError("GPT-5.6 returned duplicate rationales for a decision unit.")
        rationales[unit_id] = rationale.strip()

    if set(rationales) != expected_ids:
        raise EnrichmentError("GPT-5.6 did not return exactly one rationale for every decision unit.")
    return rationales
