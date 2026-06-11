"""Advisory scanner tests — always-exit-0 discipline and pattern coverage."""
import json
import unittest

from aerodeck_verify import advisory
from aerodeck_verify.cli import main as cli_main


class TestScanner(unittest.TestCase):
    def test_selftest_categories(self):
        findings = advisory.scan_diff(advisory.SELFTEST_DIFF)
        categories = {f["category"] for f in findings}
        for want in ("dangling-todo", "possible-credential", "debug-print",
                     "magic-number", "focused-test", "destructive-sql",
                     "deep-nesting"):
            self.assertIn(want, categories)

    def test_findings_marked_advisory(self):
        out = json.loads(advisory.format_findings(
            advisory.scan_diff(advisory.SELFTEST_DIFF)))
        self.assertTrue(out["advisory"])
        self.assertIn("never gating", out["precision_note"])

    def test_clean_diff_no_findings(self):
        self.assertEqual(advisory.scan_diff(""), [])

    def test_summarize_for_judge(self):
        findings = advisory.scan_diff(advisory.SELFTEST_DIFF)
        doc = json.loads(advisory.format_findings(findings))
        summary = advisory.summarize_for_judge(doc)
        self.assertIn("NON-GATING", summary)
        self.assertIn("[medium]", summary)

    def test_summarize_empty_is_none(self):
        self.assertIsNone(advisory.summarize_for_judge({"findings": []}))


class TestAlwaysExitZero(unittest.TestCase):
    """The advisory subcommand NEVER gates — exit 0 on every path."""

    def test_selftest_exit_0(self):
        self.assertEqual(cli_main(["advisory", "--selftest"]), 0)

    def test_missing_refs_exit_0(self):
        self.assertEqual(cli_main(["advisory"]), 0)

    def test_bad_workdir_exit_0(self):
        self.assertEqual(cli_main(["advisory", "--from", "a", "--to", "b",
                                   "--workdir", "/nonexistent/xyz"]), 0)


if __name__ == "__main__":
    unittest.main()
