"""aerodeck-verify — fail-closed verification gate for agent work.

The contract in one paragraph: a unit of agent work closes ONLY when its own
verification probe (authored by the work's creator, never the worker) runs
and its output matches the expected regex. The worker's exit code and claims
are never consulted; missing or trivial probes are rejected fail-closed; an
independent second-key judge (a different model vendor) reads the diff before
the close is even requested; and silence is never a verdict.
"""
from .gate import (  # noqa: F401
    EXIT_ERROR,
    EXIT_MISMATCH,
    EXIT_NO_SENTINELS,
    EXIT_PASS,
    EXIT_REJECTED,
    evaluate,
    extract_sentinel,
    is_tautological_expect,
    is_trivial_probe,
    run_probe,
)
# NOTE: the judge() function lives in aerodeck_verify.judge — not re-exported
# here, because rebinding the name `judge` would shadow the submodule.
from .judge import parse_verdict  # noqa: F401

__version__ = "0.1.0"
