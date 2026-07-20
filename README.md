# AgentLedger

One-line pitch: a trust and provenance layer for AI-written code — audits
Codex-driven changes before merge.

## The problem
Agentic coding can turn a small feature request into a large batch of commits
faster than a reviewer can reconstruct the intent behind each diff. Teams need
more than an author name or a green test run when deciding which AI-written
changes are routine and which touch code that deserves a careful human read.

## What it does
AgentLedger scans Git history into one DecisionUnit per changed file and commit.
It retains a clear commit-message rationale or asks GPT-5.6 to infer the likely
why from a batch of diffs. It then scores every file against an ownership map,
change size, and incident history before rendering a terminal summary and a
self-contained HTML audit report. `ledger self-report` dogfoods this exact
pipeline on AgentLedger's own real build history.

## How we used Codex and GPT-5.6
Codex accelerated the staged build: it implemented and tested the CLI skeleton,
Git ingestion, scoring, reporting, and self-report workflow one reviewable
phase at a time. The human set the product scope, fixed Python/Typer/Rich/OpenAI
stack, build order, review gates, and the decision to dogfood on this repo's
real Git history; BUILD_LOG.md records the resulting decisions and commits.

GPT-5.6 is used in `ledger enrich`, where the OpenAI Responses API returns
strict JSON-schema output for several unclear DecisionUnits in each request.
It infers a concise rationale from the commit message and diff, marks the
result as `gpt-5.6-inferred`, and leaves already-clear commit-message
rationales untouched. That model-enriched provenance is then combined with
deterministic ownership and incident scoring, rather than being used as a
single prompt-and-done review.

## Installation
```bash
git clone <repo-url>
cd codex-ledger
pip install -e .
export OPENAI_API_KEY=<your key>
# Or, use OpenRouter's GPT-5.6 route without saving a key in the repository:
export OPENROUTER_API_KEY=<your OpenRouter key>
```

## Supported platforms
macOS, Linux, and Windows (WSL recommended) — pure Python CLI, no
OS-specific dependencies.

## Try it with zero setup
```bash
ledger --demo report
open report.html   # or double-click the generated file
```

## Try it on this project's own history (dogfooding)
```bash
ledger self-report
```

## Running tests
```bash
pytest
```

## Codex Session
/feedback session ID: [fill in before submitting — use the thread that
built the core scan/enrich/score/report pipeline, phases 1-5]

## Demo video
[link]

## License
MIT License. Add the LICENSE file before making the repository public, or share
the project privately with testing@devpost.com and build-week-event@openai.com.
