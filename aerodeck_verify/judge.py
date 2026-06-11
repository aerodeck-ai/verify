"""
The second-key judge — an INDEPENDENT model reads the work and issues a verdict.

Two-key doctrine: the builder never grades its own work. A different model
(vendor) inspects the working tree against the story and answers with a final
standalone line `VERDICT: PASS` or `VERDICT: FAIL`. Anything else — silence,
timeout, a missing CLI — is NO VERDICT, and NO VERDICT is fail-closed: it
must never be relabelled as a pass, and (unlike an honest FAIL) it does not
earn a remediation round.

Exit codes (fail-closed):
  0 = VERDICT: PASS
  2 = VERDICT: FAIL
  3 = no verdict / judge timeout / any uncertainty

The judge verdict only ever gates a "verify-requested" hand-off; the close
gate (gate.py) remains the ONLY closer. This module never touches tracker
state.

The judge command is pluggable (--judge-cmd). The default is the codex CLI
in read-only mode; any command that reads a prompt as its final argument and
writes its answer to stdout works.
"""
import os
import re
import subprocess
import sys
import threading
from typing import Optional

EXIT_PASS, EXIT_FAIL, EXIT_NOVERDICT = 0, 2, 3

JUDGE_TIMEOUT_S = 900

DEFAULT_JUDGE_CMD = [
    "codex", "exec", "--skip-git-repo-check",
    "--config", 'approval_policy="never"',
    "--config", 'sandbox_mode="read-only"',
]

VERDICT_RE = re.compile(r"^\s*[#>*\-\s]*VERDICT\s*:\s*\**\s*(PASS|FAIL)\b", re.I)


def parse_verdict(text: str) -> Optional[str]:
    """Last standalone VERDICT line wins. Lines mentioning BOTH PASS and FAIL
    are the echoed prompt instruction ('VERDICT: PASS or VERDICT: FAIL') —
    skipped, so a silent judge can never inherit a verdict from its own
    instructions (fail-closed)."""
    verdict = None
    for line in text.splitlines():
        m = VERDICT_RE.match(line)
        if not m:
            continue
        upper = line.upper()
        # Instruction echo is the ONLY line shape carrying both verdict
        # tokens ("... VERDICT: PASS or VERDICT: FAIL ..."). Match those
        # standalone tokens, NOT bare PASS/FAIL substrings — prose like
        # "VERDICT: FAIL — the probe passes ..." is a real verdict and must
        # not be dropped to NO-VERDICT.
        if "VERDICT: PASS" in upper and "VERDICT: FAIL" in upper:
            continue  # instruction echo, not a verdict
        verdict = m.group(1).upper()
    return verdict


def build_prompt(*, story: str, workdir: str, advisory: Optional[str] = None) -> str:
    """Compose the verifier prompt. `story` is the work item's full context
    (title, description, sentinels). `advisory` is an OPTIONAL non-gating
    advisory block (see advisory.py) — low-precision heuristics the judge is
    explicitly told to discount unless independently confirmed."""
    advisory_block = ""
    if advisory:
        advisory_block = (
            "\n--- NON-GATING ADVISORY (low-precision heuristics) ---\n"
            f"{advisory}\n"
            "These are LOW-PRECISION heuristics — IGNORE any that are false "
            "positives. They do NOT factor into the verdict unless you "
            "independently confirm a real bug.\n"
            "--- end advisory ---\n"
        )
    return (
        "You are the independent VERIFIER (second key). "
        "A builder claims this story is complete:\n\n"
        f"{story}\n"
        f"{advisory_block}\n"
        f"Inspect the working tree at {workdir}. Run nothing destructive. "
        "Decide: does the diff/work actually satisfy the story? "
        "Reply with a final line VERDICT: PASS or VERDICT: FAIL "
        "followed by reasons."
    )


def run_judge(*, prompt: str, workdir: str, judge_cmd: Optional[list[str]] = None,
              timeout_s: int = JUDGE_TIMEOUT_S, log_path: Optional[str] = None,
              echo: bool = True):
    """Stream judge output (to log_path and/or stdout). Returns
    (full_text, rc, timed_out)."""
    cmd = list(judge_cmd or DEFAULT_JUDGE_CMD) + [prompt]
    timed_out = [False]
    lines = []
    logf = open(log_path, "w", buffering=1) if log_path else None
    try:
        proc = subprocess.Popen(cmd, cwd=workdir, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                errors="replace")

        def _kill():
            timed_out[0] = True
            try:
                proc.kill()
            except OSError:
                pass

        timer = threading.Timer(timeout_s, _kill)
        timer.start()
        try:
            for line in proc.stdout:
                lines.append(line)
                if logf:
                    logf.write(line)
                if echo:
                    sys.stdout.write(line)
                    sys.stdout.flush()
            proc.wait()
        finally:
            timer.cancel()
        if timed_out[0] and logf:
            logf.write(f"\n=== TIMEOUT after {timeout_s}s — judge killed ===\n")
    finally:
        if logf:
            logf.close()
    return "".join(lines), proc.returncode, timed_out[0]


def judge(*, story: str, workdir: str, judge_cmd: Optional[list[str]] = None,
          timeout_s: int = JUDGE_TIMEOUT_S, advisory: Optional[str] = None,
          log_path: Optional[str] = None, echo: bool = True) -> tuple[int, str]:
    """Run the full second-key pass. Returns (exit_code, outcome string)."""
    workdir = os.path.abspath(workdir)
    if not os.path.isdir(workdir):
        return EXIT_NOVERDICT, f"ERROR: workdir not a directory: {workdir}"
    prompt = build_prompt(story=story, workdir=workdir, advisory=advisory)
    try:
        text, _rc, timed_out = run_judge(
            prompt=prompt, workdir=workdir, judge_cmd=judge_cmd,
            timeout_s=timeout_s, log_path=log_path, echo=echo)
    except FileNotFoundError:
        return EXIT_NOVERDICT, "ERROR: judge command not found on PATH"

    verdict = None if timed_out else parse_verdict(text)
    if timed_out:
        return EXIT_NOVERDICT, "TIMEOUT (no verdict)"
    if verdict == "PASS":
        return EXIT_PASS, "PASS"
    if verdict == "FAIL":
        return EXIT_FAIL, "FAIL"
    return EXIT_NOVERDICT, "NO VERDICT"
