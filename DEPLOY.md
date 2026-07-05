# DEPLOY — aerodeck-ai/verify

**Target:** none (public library/CLI, not a hosted service). `aerodeck-verify` ships as
source only — no PyPI release exists yet (checked 2026-07-05: `pypi.org/pypi/aerodeck-verify/json`
returns 404) and no `.github/workflows/` directory exists in this repo.

**Runner:** manual `pip install .` by whoever needs the `verify` CLI on their box/venv.
There is no CI/CD pipeline and no build artifact registry — the repo itself is the
distribution mechanism (clone or `pip install git+https://github.com/aerodeck-ai/verify`).

**Trigger:** none automated. A consumer re-installs manually when they want to pick up
a new commit on `main`.

**Who-can-deploy:** anyone with install access to the target box/venv — this is a public
MIT-licensed CLI, not a gated production surface.

**Artifact:** the installed console-script entry point `verify` (`aerodeck_verify.cli:main`),
plus the `aerodeck_verify` Python package (`gate.py`, `judge.py`, `advisory.py`).

**Registry ID:** none — not published to PyPI or any container registry. Callers on the
Aerodeck estate consume it as a vendored/installed dependency (e.g. the `infra` repo's
`bin/aero-verified-complete` and related probe-contract shims call the installed `verify` CLI).

## Why this shape

This repo is a fail-closed verification *library*, extracted to be estate-agnostic and
publishable independently (see its own README "before/after" numbers). It has no server
component and no host it runs on — "deploy" here means "get the CLI installed somewhere it's
called from," which today is a manual `pip install .` with no automation. If a PyPI release
or a version-pinned install step is added later, update this file to match.
