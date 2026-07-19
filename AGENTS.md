# AGENTS.md — Codex Working Instructions for AgentLedger

## What this project is
AgentLedger ("Ledger") is a CLI developer tool that audits AI-agent-written
code before merge. It parses git history for a repo, reconstructs a decision
trail for each change (what changed, why, how risky), scores trust per
commit using an ownership + incident-history map, and renders a report.
Built for OpenAI Build Week, Developer Tools track.

## What we're being judged on — weigh every tradeoff against this
1. Technological Implementation — use Codex and GPT-5.6 thoroughly, not
   decoratively. A real multi-step agentic pipeline beats one prompt-and-done
   call.
2. Design — a complete, runnable product experience, not a proof of concept.
   A judge should install it and get a real report in under 5 minutes.
3. Potential Impact — every decision should serve a specific, credible
   audience: engineering teams adopting Codex/agentic coding who need to
   review AI-written diffs before merge.
4. Quality of idea — the distinctive angle is auditing AI-authored code, not
   writing code faster. Don't let the pitch drift toward "another coding
   assistant."

## Tech stack (fixed — do not change without asking)
- Python 3.11+
- CLI: Typer
- Terminal rendering: rich
- OpenAI SDK for GPT-5.6 — use the current Responses API with structured
  outputs. You (Codex) have more current knowledge of the exact API surface
  than any instruction file can hardcode — use it correctly rather than
  pattern-matching to older completion-style syntax.
- Testing: pytest
- No database, no server, no web framework. Output is one self-contained
  HTML file plus terminal output. Zero infra to run this.

## Repo layout
codex-ledger/
  agentledger/
    __init__.py
    scan.py       # git log/diff ingestion -> decision units
    enrich.py     # GPT-5.6 rationale extraction
    score.py      # ownership + incident-history risk scoring
    report.py     # HTML + terminal report rendering
    cli.py        # Typer entrypoint: scan / enrich / score / report / self-report
  .ledger/
    ownership.yaml
    incidents.json
  tests/
  sample-data/
  AGENTS.md
  SPEC.md
  README.md
  BUILD_LOG.md

## Build order — work in this order, do not skip ahead
1. Scaffold repo, CLI skeleton with all five subcommands stubbed (each
   prints "not implemented" and exits 0), pytest wired with one placeholder
   test. Commit.
2. Implement `scan`: walk git log for a path/range, extract per-commit
   diffs and messages into a DecisionUnit list. Real tests against a
   throwaway git fixture repo. Commit.
3. Implement `enrich`: where a commit message doesn't explain the "why,"
   call GPT-5.6 to infer intent from the diff. Batch requests — never one
   call per line. Use structured output so results parse reliably. Commit.
4. Implement `score`: load .ledger/ownership.yaml and .ledger/incidents.json,
   compute per-file risk and roll up to a per-commit trust score. Tests with
   clear expected scores on fixture data. Commit.
5. Implement `report`: single self-contained HTML file (inline CSS, no
   external assets) plus a matching rich terminal summary. Commit.
6. Implement `self-report`: runs the full pipeline against this repo's own
   git history and emits a ready-to-paste Markdown block for the submission
   README's "how Codex was used" section. Use our real build history as the
   demo dataset — do not fabricate a fake company scenario here.
7. Fill in real content in .ledger/ownership.yaml and .ledger/incidents.json
   (clearly-labeled sample data is fine if there's no second real repo).
8. README pass: fill every section in the existing skeleton, don't
   restructure it — it already matches Devpost's submission requirements.
9. Polish: error handling for missing repo / empty history / missing API
   key; help text; a --demo flag that runs bundled sample-data with zero
   setup so judges can test without cloning the caller's own repo.

## Guardrails
- No scope creep: no web UI, no auth, no multi-user features, no database.
  Finished phase → commit → move on, don't polish indefinitely.
- Every commit message is a real, specific sentence about what changed and
  why — this is the dogfood data for self-report and the source material
  for BUILD_LOG.md.
- After each numbered phase, append a short entry to BUILD_LOG.md: what was
  built, one real design decision and why, anything proposed-then-overridden
  in either direction.
- Prefer working and boring over clever and broken. A judge needs to run
  this in one command.
