"""
The Aerodeck close-gate contract — the pure, estate-agnostic core.

A unit of agent work reaches "done" ONLY if its OWN verification probe
(authored by the work's CREATOR at carding time, never by the worker) runs
and its output matches EXPECT. The worker's exit code / claims are NEVER
consulted.

  - no probe sentinels          -> FAIL-CLOSED, refuse close   (exit 3)
  - existence/triviality probe  -> reject, non-behavioural     (exit 4)
  - tautological EXPECT         -> reject, matches anything    (exit 4)
  - EXPECT not a valid regex    -> reject                      (exit 4)
  - probe output mismatch       -> refuse close                (exit 5)
  - probe output matches        -> pass                        (exit 0)
  - runner / tracker errors     -> refuse close                (exit 2)

Sentinels in the work item's description:
  ### VERIFICATION-PROBE: <shell command, behavioural>
  ### VERIFICATION-EXPECT: <regex the probe output (stdout+stderr) must match>

This module is intentionally stdlib-only and import-free of the rest of the
package, so a consumer can load this single file and get the whole contract.
"""
import re
import subprocess
from typing import Optional

EXIT_PASS = 0
EXIT_ERROR = 2
EXIT_NO_SENTINELS = 3
EXIT_REJECTED = 4
EXIT_MISMATCH = 5

PROBE_TIMEOUT_S = 60


def extract_sentinel(description: str, name: str) -> Optional[str]:
    for line in (description or "").splitlines():
        m = re.match(rf"^#{{0,4}}\s*{name}:\s*(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    return None


# Output-fabrication and existence/liveness commands: a probe whose first token (or
# any pipeline stage's first token) merely prints literals or checks existence is
# not behavioural evidence. Fail-closed: over-rejecting is acceptable, under- is not.
TRIVIAL_PATTERNS = [
    r"^(echo|printf|true|:|cat|yes)(\s|$)",
    # Fabricating output later in a pipeline. Literal-only echo/printf stages are
    # fabrication; echo of COMPUTED values (args containing a $ expansion, e.g.
    # `echo "rc=$rc ran=$ran"`) is legitimate result-surfacing for EXPECT matching
    # — the evidence was computed by earlier behavioural stages. `yes` is always
    # fabrication. (Refined 2026-06-11: literal-vs-computed split; was rejecting
    # every probe that surfaced its results via echo.)
    r"(\||;|&&)\s*(echo|printf)\s+(?![^|;&]*\$)",
    r"(\||;|&&)\s*yes(\s|$)",
    r"test\s+-[ef](\s|$)",
    r"(^|\s)ls(\s|$)",
    r"systemctl\s+is-active",
    r"(^|\s)pgrep(\s|$)",
    r"(^|\s)stat(\s|$)",
]

# Backwards-compatible alias for consumers that shadowed the private name.
_TRIVIAL = TRIVIAL_PATTERNS


def is_trivial_probe(probe: str) -> bool:
    return any(re.search(p, probe, re.IGNORECASE) for p in TRIVIAL_PATTERNS)


def is_tautological_expect(expect: str) -> bool:
    literal = re.sub(r"[][(){}.\^$*+?|\\-]", "", expect)
    literal = re.sub(r"[^a-zA-Z0-9]", "", literal)
    return len(literal) == 0


def run_probe(probe: str, timeout_s: int = PROBE_TIMEOUT_S) -> str:
    try:
        r = subprocess.run(probe, shell=True, capture_output=True, text=True,
                           timeout=timeout_s)
        return r.stdout + r.stderr
    except subprocess.TimeoutExpired:
        return "PROBE-TIMEOUT"
    except Exception as e:  # noqa: BLE001 — gate must never crash on a probe
        return f"PROBE-ERROR: {e}"


def evaluate(*, description: Optional[str] = None,
             probe: Optional[str] = None,
             expect: Optional[str] = None,
             timeout_s: int = PROBE_TIMEOUT_S) -> tuple[int, list[str]]:
    """Run the full gate contract. Returns (exit_code, log messages).

    The messages are exactly what the reference gate prints (after its
    `GATE[<id>] ` prefix) — consumers that need byte-identical output
    prefix each message themselves.

    Checks run in contract order: sentinels -> trivial probe -> tautological
    EXPECT -> probe execution -> regex validity -> match. (Regex validity is
    checked at match time, after the probe runs — the reference order.)
    """
    if description is not None:
        probe = extract_sentinel(description, "VERIFICATION-PROBE")
        expect = extract_sentinel(description, "VERIFICATION-EXPECT")

    if not probe or not expect:
        return EXIT_NO_SENTINELS, [
            "BLOCK (fail-closed): missing VERIFICATION-PROBE/EXPECT sentinels"]
    if is_trivial_probe(probe):
        return EXIT_REJECTED, [
            f"BLOCK: probe is existence/fabrication class, not behavioural: [{probe}]"]
    if is_tautological_expect(expect):
        return EXIT_REJECTED, [
            f"BLOCK: tautological EXPECT (matches anything): [{expect}]"]

    actual = run_probe(probe, timeout_s=timeout_s)
    try:
        matched = bool(re.search(expect, actual))
    except re.error as e:
        return EXIT_REJECTED, [f"BLOCK: EXPECT is not a valid regex ({e})"]

    if not matched:
        return EXIT_MISMATCH, [
            "FAIL: probe output did not match EXPECT — close refused",
            f"  EXPECT=[{expect}]",
            f"  ACTUAL=[{actual[:300]}]",
        ]
    return EXIT_PASS, ["PASS: probe matched EXPECT"]
