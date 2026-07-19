# AgentLedger

One-line pitch: a trust and provenance layer for AI-written code — audits
Codex-driven changes before merge.

## The problem
[Fill in: 2-3 sentences on why teams adopting agentic coding need this.]

## What it does
[Fill in: scan -> enrich -> score -> report pipeline, 3-4 sentences.]

## How we used Codex and GPT-5.6
[Required by the submission rules — fill in as you build, pulling directly
from BUILD_LOG.md. Cover specifically:
- Where Codex accelerated the workflow
- Which product/engineering/design decisions were made by a human vs
  proposed by Codex
- How GPT-5.6 specifically contributed to the final result — which step(s)
  call the model and why]

## Installation
```bash
git clone <repo-url>
cd codex-ledger
pip install -e .
export OPENAI_API_KEY=<your key>
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
[Add a LICENSE file — MIT is simplest — before making the repo public,
or share privately with testing@devpost.com and build-week-event@openai.com]
