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
- Built: Added ownership and incident configuration loading, per-file
  `RiskScore` calculation, per-commit `TrustScore` rollups, flagged-hunk
  reasons, and JSON stdin/stdout support for `ledger score`.
- Decision made and why: Made risk scoring deterministic and transparent:
  ownership criticality, diff size, and prior incidents are separately visible
  inputs, while a commit's trust score is one minus its average file risk.
- Codex proposed vs what we changed: With user approval, Codex added PyYAML to
  load the required ownership configuration reliably; no other product or
  architecture decision was overridden.

## Phase 5 — report
- Built: Added a single-file HTML audit report with inline CSS and a matching
  Rich terminal summary. Both show each commit's trust score, rationale trail,
  diff hunks, and explicit flagged-hunk reasons.
- Decision made and why: Used strongly separated red high-risk and green
  low-risk cards/panels so the review priority reads immediately in a terminal
  recording or a demo-video frame.
- Codex proposed vs what we changed: Codex preserved DecisionUnits in the
  score command's JSON envelope so the report can render the full pipeline
  trail; no product or architecture decision was overridden.

## Phase 6 — self-report
- Built: Added `ledger self-report`, which runs scan, enrich, score, and report
  against AgentLedger's own first-commit-to-HEAD history, writes a self-audit
  HTML file, and emits README-ready Markdown from real commits and BUILD_LOG.
- Decision made and why: Kept the Markdown tied to the actual build trail and
  phase log, so the Devpost provenance story is auditable rather than a
  fabricated company scenario.
- Codex proposed vs what we changed: Codex used the requested dogfooding path
  and mocked the API only in tests; no product or architecture decision was
  overridden.

## Phase 7 — ledger data
- Built: Added AgentLedger's own ownership map and three clearly-labelled
  sample incidents for the enrichment, scoring, and scanning modules. The
  records use real paths while remaining explicit that they are demo data.
- Decision made and why: Marked the model-facing enrichment and trust-score
  calculation modules as high criticality, so self-report visibly demonstrates
  why an AI-authored change there merits a reviewer pass.
- Codex proposed vs what we changed: Codex used real repository files and
  explicit sample labels because no real production incident history exists;
  no product or architecture decision was overridden.

## Phase 8 — README
- Built: Completed every README submission section with the real pipeline,
  commit trail, and GPT-5.6 usage story, while leaving the feedback-session ID
  and demo-video link for manual submission-time entry.
- Decision made and why: Grounded the README's provenance narrative in
  BUILD_LOG.md and the self-report's real Git-history summary instead of
  inventing a company or a production incident record.
- Codex proposed vs what we changed: Codex drafted the README from the recorded
  build trail; the human-owned session ID and demo URL remain placeholders as
  requested.

## Phase 9 — polish
- Built:
- Decision made and why:
- Codex proposed vs what we changed:
