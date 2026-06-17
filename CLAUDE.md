# CLAUDE.md — verify

> Repo-level guidance for Claude Code / Codex seats working in this repo.
> Inherits the estate-wide rules in ~/CLAUDE.md (AGENTS.md): identity, safety lines, credential rules, "GitHub main is the single source of truth".

## What this is
`aerodeck-verify` — a fail-closed verification gate for agent work, extracted as an
estate-agnostic CLI (public, MIT). A work item closes ONLY if its own verification
probe runs and its output matches EXPECT; probe + EXPECT are authored at carding time
by the creator, never the worker, and the worker's exit code is never consulted.

## Stack & layout
- Python ≥3.10, setuptools, console-script entry point `verify = aerodeck_verify.cli:main`.
- `aerodeck_verify/` — `cli.py`, `gate.py` (probe contract + trivial-probe rejector),
  `judge.py` (independent second-key model verdict), `advisory.py` (non-gating diff scanner).
- `tests/` — `test_gate.py`, `test_judge.py`, `test_advisory.py`, `test_cli.py`.

## Build / run / test
```bash
pip install .                                   # install the `verify` CLI

verify probe --id kt_123 --description-file card.md      # gate by sentinel description
verify probe --id kt_123 --probe '<cmd>' --expect '^ok$' # or pass probe/expect directly
verify judge --story-file story.md --workdir /path       # second-key model verdict
verify advisory --from main --to HEAD                    # advisory diff scan (always exit 0)
```
Exit codes: 0 pass · 2 runner/error · 3 no probe/no verdict (fail-closed) · 4 trivial/tautological · 5 mismatch.
Run tests with `pytest` (test deps not pinned in pyproject — install pytest manually).

## Conventions
- Default branch: `main` — single source of truth; additive commits or PRs; never force-push main.
- Public repo — no secrets, no estate-internal hostnames/IDs in code or commits.
- The CLI is the contract, not the tracker: trackers wire a thin shim that calls `verify probe`
  and closes only on exit 0. Fail-closed is load-bearing — never relax it to "pass on silence".
