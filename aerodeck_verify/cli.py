"""
aerodeck-verify CLI — `verify <subcommand>`.

Subcommands:
  probe     run the close-gate contract on a work item's sentinels (exit 0/2/3/4/5)
  judge     run the second-key judge over a working tree (exit 0/2/3)
  advisory  scan a git diff range for non-gating findings (always exit 0)

`verify probe` emits exactly the reference gate's log lines (`GATE[<id>] ...`)
and exit codes, so an estate gate can shim onto it byte-identically. Tracker
integration (fetching the item, closing it) stays in the consumer — this CLI
is the contract, not the tracker.
"""
import argparse
import json
import os
import sys
from typing import Optional

from . import advisory as advisory_mod
from . import gate
from . import judge as judge_mod


def _read_description(args) -> Optional[str]:
    if args.description_file == "-":
        return sys.stdin.read()
    if args.description_file:
        with open(args.description_file) as fh:
            return fh.read()
    return None


def cmd_probe(args) -> int:
    item_id = args.id
    description = _read_description(args)
    if description is not None:
        code, msgs = gate.evaluate(description=description,
                                   timeout_s=args.timeout)
    else:
        code, msgs = gate.evaluate(probe=args.probe, expect=args.expect,
                                   timeout_s=args.timeout)
    for msg in msgs:
        print(f"GATE[{item_id}] {msg}", flush=True)
    return code


def cmd_judge(args) -> int:
    if args.story_file == "-":
        story = sys.stdin.read()
    else:
        with open(args.story_file) as fh:
            story = fh.read()
    advisory_text = None
    if args.advisory_file:
        try:
            with open(args.advisory_file) as fh:
                advisory_text = advisory_mod.summarize_for_judge(json.load(fh))
        except Exception:
            advisory_text = None  # advisory is best-effort, never fatal
    judge_cmd = args.judge_cmd.split() if args.judge_cmd else None
    code, outcome = judge_mod.judge(
        story=story, workdir=args.workdir, judge_cmd=judge_cmd,
        timeout_s=args.timeout, advisory=advisory_text,
        log_path=args.log, echo=not args.quiet)
    print(f"verdict={outcome} exit={code}")
    return code


def cmd_advisory(args) -> int:
    if args.selftest:
        advisory_mod.selftest()
        return 0  # always exit 0 — advisory only
    if not args.from_ref or not args.to_ref:
        print("ERROR: --from and --to are required", file=sys.stderr)
        return 0  # always exit 0
    workdir = os.path.abspath(args.workdir)
    if not os.path.isdir(workdir):
        print(f"ERROR: workdir not a directory: {workdir}", file=sys.stderr)
        return 0
    try:
        diff_text = advisory_mod.run_git_diff(
            from_ref=args.from_ref, to_ref=args.to_ref, workdir=workdir)
    except Exception as e:
        print(f"ERROR: git diff failed: {e}", file=sys.stderr)
        diff_text = ""
    findings = advisory_mod.scan_diff(diff_text)
    print(advisory_mod.format_findings(findings, args.audience))
    return 0  # always exit 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="verify",
        description="aerodeck-verify — fail-closed verification gate for agent work")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("probe", help="run the close-gate contract (exit 0/3/4/5)")
    p.add_argument("--id", default="item", help="work-item id for log lines")
    p.add_argument("--description-file", metavar="PATH",
                   help="file holding the item description with "
                        "### VERIFICATION-PROBE/EXPECT sentinels ('-' = stdin)")
    p.add_argument("--probe", help="probe command (alternative to --description-file)")
    p.add_argument("--expect", help="expected-output regex (with --probe)")
    p.add_argument("--timeout", type=int, default=gate.PROBE_TIMEOUT_S,
                   help=f"probe timeout seconds (default {gate.PROBE_TIMEOUT_S})")
    p.set_defaults(func=cmd_probe)

    j = sub.add_parser("judge", help="run the second-key judge (exit 0/2/3)")
    j.add_argument("--story-file", required=True, metavar="PATH",
                   help="file holding the story/work-item context ('-' = stdin)")
    j.add_argument("--workdir", default=os.getcwd(),
                   help="working tree to inspect (default: cwd)")
    j.add_argument("--judge-cmd", default=None,
                   help="judge command line (default: codex exec, read-only)")
    j.add_argument("--advisory-file", default=None, metavar="PATH",
                   help="optional advisory JSON to weave in (non-gating)")
    j.add_argument("--timeout", type=int, default=judge_mod.JUDGE_TIMEOUT_S,
                   help=f"judge timeout seconds (default {judge_mod.JUDGE_TIMEOUT_S})")
    j.add_argument("--log", default=None, help="tee judge output to this file")
    j.add_argument("--quiet", action="store_true", help="do not echo judge output")
    j.set_defaults(func=cmd_judge)

    a = sub.add_parser("advisory",
                       help="scan a git diff range — non-gating, always exit 0")
    a.add_argument("--from", dest="from_ref", help="git ref to diff from")
    a.add_argument("--to", dest="to_ref", help="git ref to diff to")
    a.add_argument("--workdir", default=os.getcwd(),
                   help="working directory (default: cwd)")
    a.add_argument("--audience", choices=["agent", "human"], default="agent")
    a.add_argument("--selftest", action="store_true",
                   help="run the scanner self-test and exit")
    a.set_defaults(func=cmd_advisory)
    return ap


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
