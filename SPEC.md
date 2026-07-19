# SPEC.md — Functional Specification

## One-line pitch
A CLI tool that audits AI-agent-written code changes before merge:
reconstructs why each change was made, flags high-risk changes against an
ownership/incident map, and produces a per-commit trust score.

## Primary user story
An engineering team has adopted Codex/agentic coding. A tech lead runs
`ledger scan .` before approving a batch of agent-generated commits and
gets a report showing which hunks are low-risk boilerplate versus which
touch a critical, previously-incident-prone module and need a careful
human read.

## Data model

### DecisionUnit — one per changed file per commit
- commit_sha: str
- file_path: str
- diff_hunk: str (patch text, truncated if huge)
- commit_message: str
- author: str
- timestamp: ISO8601
- rationale: str | null              # filled by enrich if not already clear
- rationale_source: "commit_message" | "gpt-5.6-inferred"

### RiskScore — one per DecisionUnit
- file_path: str
- criticality: float (0-1, from ownership.yaml + incident history match)
- change_size_factor: float (0-1, larger diffs in one file score higher)
- incident_history_hit: bool
- risk_score: float (0-1 combined)

### TrustScore — one per commit or range
- commit_sha / range
- overall_score: float (0-1, higher = more trustworthy)
- flagged_hunks: list of {file_path, reason}
- summary: str (one human-readable paragraph)

## ownership.yaml schema (sample)
```yaml
paths:
  "src/auth/**": { owner: "security-team", criticality: high }
  "src/billing/**": { owner: "payments-team", criticality: high }
  "docs/**": { owner: "any", criticality: low }
  "**": { owner: "unassigned", criticality: medium }
```

## incidents.json schema (sample)
```json
[
  {
    "id": "INC-001",
    "files": ["src/auth/session.py"],
    "summary": "session token not invalidated on logout",
    "date": "2025-11-02"
  }
]
```

## CLI surface
- `ledger scan <path> [--since <git-ref>]`
- `ledger enrich`
- `ledger score`
- `ledger report [--out report.html]`
- `ledger self-report` — runs all four steps against this repo's own
  history, plus emits README-ready Markdown
- `--demo` flag on any command — runs against bundled sample-data/ instead
  of requiring the caller's own repo

## MVP definition of done
- `ledger --demo report` produces a working HTML report from bundled
  sample data with zero setup beyond `pip install` and an API key
- `ledger self-report` produces a real report from this project's own git
  history
- At least one flagged high-risk hunk and one low-risk hunk appear
  visibly differently in the output
- pytest suite passes for scan and score logic (deterministic, no live
  API calls in tests — mock the GPT-5.6 calls)

## Explicit non-goals — do not build these
- No live GitHub/GitLab webhook integration
- No web dashboard or server
- No multi-repo or team/org features
- No auth or user accounts
