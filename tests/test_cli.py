"""CLI tests — `verify probe` log-line and exit-code surface.

The probe subcommand's output is contract: `GATE[<id>] <message>` lines and
exit codes 0/3/4/5, byte-identical to the reference estate gate so shims can
sit on top without translation.
"""
import contextlib
import io
import os
import tempfile
import unittest

from aerodeck_verify.cli import main as cli_main


def run_cli(argv):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli_main(argv)
    return code, buf.getvalue()


class TestProbeCommand(unittest.TestCase):
    def test_no_sentinels_exit_3(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("prose only, no sentinels")
            path = fh.name
        try:
            code, out = run_cli(["probe", "--id", "abc",
                                 "--description-file", path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 3)
        self.assertEqual(
            out,
            "GATE[abc] BLOCK (fail-closed): missing VERIFICATION-PROBE/EXPECT sentinels\n")

    def test_trivial_probe_exit_4(self):
        code, out = run_cli(["probe", "--id", "abc",
                             "--probe", "echo done", "--expect", "done"])
        self.assertEqual(code, 4)
        self.assertEqual(
            out,
            "GATE[abc] BLOCK: probe is existence/fabrication class, "
            "not behavioural: [echo done]\n")

    def test_tautological_expect_exit_4(self):
        code, out = run_cli(["probe", "--id", "abc",
                             "--probe", "curl -s http://x/health",
                             "--expect", ".*"])
        self.assertEqual(code, 4)
        self.assertIn("tautological EXPECT", out)

    def test_mismatch_exit_5(self):
        code, out = run_cli(["probe", "--id", "abc",
                             "--probe", "seq 3", "--expect", "^banana$"])
        self.assertEqual(code, 5)
        self.assertIn("GATE[abc] FAIL: probe output did not match EXPECT", out)
        self.assertIn("GATE[abc]   EXPECT=[^banana$]", out)

    def test_match_exit_0(self):
        code, out = run_cli(["probe", "--id", "abc",
                             "--probe", "seq 3",
                             "--expect", r"(^|\n)2(\n|$)"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "GATE[abc] PASS: probe matched EXPECT\n")

    def test_description_sentinel_path(self):
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
            fh.write("### VERIFICATION-PROBE: seq 2\n"
                     "### VERIFICATION-EXPECT: (^|\\n)2(\\n|$)\n")
            path = fh.name
        try:
            code, _ = run_cli(["probe", "--id", "x", "--description-file", path])
        finally:
            os.unlink(path)
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
