# aerodeck-verify

**A fail-closed verification gate for agent work.** An agent's claim that its
work is done is not evidence. This is the gate we run our own software factory
on, extracted as an estate-agnostic CLI.

## Why this exists — before / after

Before the gate, on our own production fleet, we measured how often an agent's
"done" self-report survived an independent re-probe:

- **83%** of completion claims were false in two deep review audits
  (FACTORY-DEEP-REVIEW / ENGINEERING-AND-CAPACITY-REVIEW).
- **72%** in the outcome-tester profile audit — high enough that a dedicated
  agent existed solely to re-verify other agents' achievements.
- **45%** true-lie rate across a month of "done" claims in a week-retrospective
  reality audit: 454 files in one month carried status claims the audit proved
  untrue.

After the gate, a work item cannot reach "done" on a self-report at all. The
gate runs a probe that was authored by the work's *creator* before the worker
ever saw the item, checks the probe's real output against a regex, and refuses
everything else — fail-closed. The numbers above are the before; the after is
structural: the lying channel (worker exit codes and claims) is simply not an
input. We have not "regenerated" or solved model honesty — we removed
self-reporting from the trust path.

## The contract

A unit of agent work closes ONLY if its own verification probe runs and its
output matches EXPECT. Probe and EXPECT are authored at carding time by the
item's creator, **never** by the worker. The worker's exit code is never
consulted.

| Condition | Exit |
|---|---|
| probe output matches EXPECT | **0** |
| runner / tracker errors | **2** |
| no probe sentinels on the item | **3** (fail-closed) |
| trivial probe (existence / fabrication class) | **4** |
| tautological EXPECT (matches anything) / invalid regex | **4** |
| probe output does not match EXPECT | **5** |

Sentinels live in the work item's description:

```
### VERIFICATION-PROBE: curl -s http://localhost:8080/health
### VERIFICATION-EXPECT: ^ok$
```

### The trivial-probe rejector

A probe that merely proves existence (`test -e`, `ls`, `stat`, `pgrep`,
`systemctl is-active`) or fabricates its own output (`echo done`, `printf ok`,
`yes` — including as a trailing pipeline stage) is rejected as
non-behavioural, exit 4. Echo of *computed* values (`echo "rc=$rc"`) is
allowed — the evidence was produced by earlier behavioural stages. The
rejector is deliberately over-eager: over-rejecting is acceptable,
under-rejecting is not.

## Usage

```bash
pip install .

# Gate a work item by its description file (sentinels inside)
verify probe --id kt_123 --description-file card.md

# Or pass probe/expect directly
verify probe --id kt_123 --probe 'curl -s http://localhost:8080/health' --expect '^ok$'

# Second-key judge: an INDEPENDENT model reads the tree and issues a verdict
verify judge --story-file story.md --workdir /path/to/worktree
# exit 0 = VERDICT: PASS, 2 = VERDICT: FAIL, 3 = no verdict (fail-closed)

# Advisory diff scan — non-gating, always exit 0
verify advisory --from main --to HEAD
```

## The second key

The builder never grades its own work. `verify judge` runs a *different*
model (default: the `codex` CLI, read-only sandbox; pluggable via
`--judge-cmd`) over the working tree with the story, and parses the last
standalone `VERDICT: PASS` / `VERDICT: FAIL` line of its output.

Silence is never a verdict: a timeout, a missing CLI, or output with no
verdict line is exit 3, NO VERDICT — distinct from an honest FAIL (exit 2)
and never relabelled as a pass. The verdict parser skips the echoed prompt
instruction ("VERDICT: PASS or VERDICT: FAIL") but keeps real verdicts whose
prose happens to contain the other token — a real `VERDICT: FAIL — the probe
passes, but …` is a FAIL, not silence.

The judge only gates the hand-off to the close gate; it never closes anything
itself.

## The advisory scanner

`verify advisory` scans a git diff range for low-precision review heuristics
(dangling TODOs, possible hardcoded credentials, focused tests, destructive
SQL, …) and emits JSON findings. It is **advisory-only by ruling**: it always
exits 0, and when its findings are woven into the judge prompt they are
explicitly marked non-gating (~12% estimated precision) — the judge is told
to ignore anything it cannot independently confirm.

## Wiring it into your own tracker

This CLI is the contract, not the tracker. Your estate keeps a thin shim that
(a) fetches the work item from your board, (b) calls `verify probe`, and
(c) closes the item only on exit 0. `verify probe` emits `GATE[<id>] …` log
lines and the exit codes above, byte-identical to the reference estate gate,
so a shim needs no translation layer.

## License

MIT
