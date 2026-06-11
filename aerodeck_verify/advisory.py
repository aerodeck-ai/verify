"""
Advisory diff scanner — ADVISORY-ONLY, NEVER A GATE.

Scans a committed git diff range for low-signal review patterns and emits
non-gating JSON findings. Always exits 0 — by ruling, advisory output may
inform the second-key judge (judge.py weaves it into the prompt as an
explicitly discountable block) but it never decides anything by itself.
Estimated precision is ~12%: these are tripwires for a human or judge to
glance at, not evidence.
"""
import json
import re
import subprocess
from datetime import datetime, timezone

PRECISION_NOTE = "~12% estimated precision — advisory only, never gating"

# Each pattern is (regex, severity, category, short_message).
# These are LOW-PRECISION heuristics (~12% precision — advisory only, never gating).
ADVISORY_PATTERNS = [
    # Magic numbers (5+ digit integer literals — excluding common 10000-ish)
    (r'(?<!\w)(?<![.\w])(?:[1-9]\d{4,})(?![\w.])',
     "info", "magic-number", "Large integer literal — magic number?"),
    # Commented-out code blocks (// or # followed by code-like keywords)
    (r'(?i)^\s*(?://|#)\s*(?:if|for|while|function|def|const|let|var|return|import|export|async|await|class)\b',
     "info", "commented-code", "Commented-out code block"),
    # TODO / FIXME / HACK without a work-item reference
    (r'(?i)(?:TODO|FIXME|HACK)(?!\s*[\(\[\{]\s*(?:kt_|#\d+|OCS-\d+|CARD))',
     "low", "dangling-todo", "TODO/FIXME/HACK without a card reference"),
    # console.log / print statements (potential debug leftover)
    (r'\bconsole\.(?:log|debug|warn|info)\s*\(', "info", "debug-print",
     "Console debug statement — intentional?"),
    # Hardcoded secrets pattern (high-entropy looking strings)
    (r'(?i)(?:api[_-]?key|secret|password|token|bearer)\s*[:=]\s*["\'][^\'"]{8,}["\']',
     "medium", "possible-credential", "Possible hardcoded credential"),
    # Large files (>500 lines added in a single diff file)
    (None, "info", "large-diff", None),  # special: handled post-diff
    # Excessive nesting indicators (deep indent in a diff addition line)
    (r'^\s{33,}\S', "info", "deep-nesting", "Line with deep nesting (≥8 levels)"),
    # .only() in test files (accidental focused test)
    (r'(?i)\b(?:it|describe|test|context)\.only\s*\(', "medium", "focused-test",
     ".only() call in test — accidental focus?"),
    # Non-idempotent mutation without rollback comment
    (r'(?i)\b(?:DROP|DELETE|TRUNCATE|ALTER)\s+(?:TABLE|DATABASE|INDEX)\b(?!.*rollback)',
     "medium", "destructive-sql", "Destructive SQL without rollback comment"),
]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")


def run_git_diff(*, from_ref: str, to_ref: str, workdir: str) -> str:
    """Run `git diff from_ref..to_ref` and return the unified diff text."""
    cmd = ["git", "-C", workdir, "diff", f"{from_ref}..{to_ref}"]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace",
                          timeout=120)
    return proc.stdout


def diff_stats(diff_text: str):
    """Return (file_count, total_additions, files_modified)."""
    files = set()
    additions = 0
    files_modified = 0
    for line in diff_text.splitlines():
        if line.startswith("diff --git"):
            files_modified += 1
        elif line.startswith("--- a/") or line.startswith("+++ b/"):
            m = re.search(r'[ab]/(.+)', line)
            if m:
                files.add(m.group(1))
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
    return len(files), additions, files_modified


def scan_diff(diff_text: str) -> list[dict]:
    """Run advisory patterns over the diff. Returns list of finding dicts."""
    findings = []
    current_file = None
    current_line_num = 0

    for line in diff_text.splitlines():
        # Track file and line number in the diff
        fm = re.match(r'^\+\+\+ b/(.+)', line)
        if fm:
            current_file = fm.group(1)
            current_line_num = 0
            continue

        # Track the new file's line numbers from @@ hunks
        hm = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@', line)
        if hm:
            current_line_num = int(hm.group(1)) - 1
            continue

        if line.startswith("+"):
            current_line_num += 1
        elif not line.startswith("-"):
            # Context line (unchanged) — still in the new file, increment
            current_line_num += 1
        # Deletion-only lines don't increment the new-file counter

        # Only scan added lines (+)
        if not line.startswith("+") or line.startswith("+++"):
            continue

        content = line[1:]  # strip the + prefix

        for pattern, severity, category, message in ADVISORY_PATTERNS:
            if pattern is None:
                continue  # special patterns handled later
            m = re.search(pattern, content)
            if m:
                findings.append({
                    "severity": severity,
                    "category": category,
                    "message": message,
                    "file": current_file or "(unknown)",
                    "line": current_line_num,
                    "snippet": content.strip()[:120],
                    "match": m.group(0)[:80],
                })

    # Post-diff stats: file count and size
    file_count, total_adds, files_mod = diff_stats(diff_text)
    if file_count >= 10:
        findings.append({
            "severity": "info",
            "category": "large-diff",
            "message": f"Large diff: {file_count} files, {total_adds} lines added across {files_mod} changes",
            "file": "(diff summary)",
            "line": 0,
            "snippet": f"{file_count} files / {total_adds}+ lines",
            "match": "",
        })

    return findings


def format_findings(findings: list[dict], audience: str = "agent") -> str:
    """JSON output with metadata — audience 'agent' is the structured form."""
    return json.dumps({
        "audience": audience,
        "generated_at": now(),
        "finding_count": len(findings),
        "advisory": True,
        "precision_note": PRECISION_NOTE,
        "findings": findings,
    }, indent=2)


def summarize_for_judge(findings_doc: dict) -> str | None:
    """Compact, non-gating summary block for the judge prompt. None if the
    document carries no findings."""
    findings = findings_doc.get("findings") or []
    if not findings:
        return None
    by_sev = {}
    for f in findings:
        by_sev.setdefault(f.get("severity", "info"), []).append(f)
    lines = [
        f"ADVISORY ({findings_doc.get('finding_count', len(findings))} findings — "
        f"NON-GATING, advisory only, ~12 % precision):",
    ]
    for sev in ("medium", "low", "info"):
        items = by_sev.get(sev, [])
        if not items:
            continue
        lines.append(f"  [{sev}]")
        for f in items[:12]:  # cap per severity
            lines.append(
                f"    - {f.get('file', '?')}:{f.get('line', '?')} "
                f"({f.get('category', '?')}) {f.get('message', '')}"
            )
        if len(items) > 12:
            lines.append(f"    ... and {len(items) - 12} more [{sev}]")
    return "\n".join(lines)


SELFTEST_DIFF = """\
diff --git a/src/lib/Demo.ts b/src/lib/Demo.ts
index 0000000..1111111 100644
--- a/src/lib/Demo.ts
+++ b/src/lib/Demo.ts
@@ -1,0 +1,10 @@
+// TODO fix this later
+const API_KEY = "sk-abc123def456notreal"
+console.log("debug here", 12345)
+describe.only("test suite", () => {
+  DROP TABLE users
+// deeply-nested line prefixed with '+' then many spaces:
+                                  deeply_nested_call()
+})
"""


def selftest() -> bool:
    """Run patterns against a synthetic diff — verify the scanner works."""
    findings = scan_diff(SELFTEST_DIFF)
    categories = {f["category"] for f in findings}
    expected = {"dangling-todo", "possible-credential", "debug-print",
                "magic-number", "focused-test", "destructive-sql", "deep-nesting"}
    missing = expected - categories
    if missing:
        import sys
        print(f"[{now()}] SELFTEST FAIL: missing categories: {missing}", file=sys.stderr)
        return False
    print("ADVISORY-SELFTEST-OK")
    return True
