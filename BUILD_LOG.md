# BUILD_LOG.md

Running log of what got built and why. Append one entry per phase from
AGENTS.md's build order. This is the raw material for the README's "How we
used Codex" section and for `ledger self-report`'s summary.

## Phase 1 — Scaffold
- Built: Packaged the `agentledger` Python module, five Typer CLI command
  stubs (`scan`, `enrich`, `score`, `report`, and `self-report`), and a pytest
  wiring check that invokes the scan stub.
- Decision made and why: Added every later pipeline module as an empty,
  documented file now so the required project layout is stable from the first
  commit, while keeping all behavior explicitly stubbed until its phase.
- Codex proposed vs what we changed: Codex followed the specified fixed stack
  and phase order; no product or architecture proposal was overridden.

## Phase 2 — scan
- Built: Implemented git-history scanning into one `DecisionUnit` per changed
  file per commit, with commit metadata, full patch text, a configurable
  large-diff truncation boundary, `--since` range support, and JSON CLI output.
- Decision made and why: Used Git's native commit/file/diff plumbing instead
  of parsing a combined patch stream, which keeps each decision unit reliably
  scoped to exactly one changed file.
- Codex proposed vs what we changed: Codex followed the requested range
  semantics (`<since>..HEAD`) and tested against a throwaway repository; no
  product or architecture decision was overridden.

## Phase 3 — enrich
- Built: Added batched GPT-5.6 rationale enrichment through the Responses API,
  using strict JSON-schema structured output and JSON stdin/stdout for the CLI.
  Clear commit-message rationales are retained locally; unclear units are
  enriched in batches and marked `gpt-5.6-inferred`.
- Decision made and why: Used one strict structured-output response per small
  batch rather than a request per diff, so the pipeline is both reliable to
  parse and practical for a commit range with many changed files.
- Codex proposed vs what we changed: Codex used the requested GPT-5.6 Responses
  API and local commit-message heuristic; no product or architecture decision
  was overridden.

## Phase 4 — score
- Built:
- Decision made and why:
- Codex proposed vs what we changed:

## Phase 5 — report
- Built:
- Decision made and why:
- Codex proposed vs what we changed:

## Phase 6 — self-report
- Built:
- Decision made and why:
- Codex proposed vs what we changed:

## Phase 7-9 — data, README, polish
- Built:
- Decision made and why:
- Codex proposed vs what we changed:
