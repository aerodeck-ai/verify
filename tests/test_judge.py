"""Judge tests — verdict parsing (incl. the instruction-echo regression) and
the pluggable judge command path."""
import os
import tempfile
import unittest

from aerodeck_verify import judge as judge_mod


class TestParseVerdict(unittest.TestCase):
    def test_plain_verdicts(self):
        self.assertEqual(judge_mod.parse_verdict("VERDICT: PASS"), "PASS")
        self.assertEqual(judge_mod.parse_verdict("VERDICT: FAIL"), "FAIL")

    def test_fail_verdict_whose_prose_says_passes(self):
        # The regression that motivated the parsefix: a real FAIL verdict whose
        # own prose contains the word "passes" must NOT be dropped to NO-VERDICT.
        text = "VERDICT: FAIL — the probe passes and the code compiles, but ..."
        self.assertEqual(judge_mod.parse_verdict(text), "FAIL")

    def test_pass_verdict_whose_prose_mentions_failures(self):
        text = "VERDICT: PASS — earlier failures were fixed."
        self.assertEqual(judge_mod.parse_verdict(text), "PASS")

    def test_instruction_echo_is_no_verdict(self):
        text = ("Reply with a final line VERDICT: PASS or VERDICT: FAIL "
                "followed by reasons.")
        self.assertIsNone(judge_mod.parse_verdict(text))

    def test_last_verdict_wins(self):
        text = "VERDICT: PASS\nsome reconsideration\nVERDICT: FAIL"
        self.assertEqual(judge_mod.parse_verdict(text), "FAIL")

    def test_markdown_decorated_verdict(self):
        self.assertEqual(judge_mod.parse_verdict("- **VERDICT: PASS**"), "PASS")

    def test_silence_is_no_verdict(self):
        self.assertIsNone(judge_mod.parse_verdict(""))
        self.assertIsNone(judge_mod.parse_verdict("I am not sure about this."))


class TestJudgeRunner(unittest.TestCase):
    """Drive judge() with stub judge commands — no real model involved."""

    def _judge(self, judge_cmd, timeout_s=30):
        return judge_mod.judge(story="STORY: do the thing", workdir=os.getcwd(),
                               judge_cmd=judge_cmd, timeout_s=timeout_s,
                               echo=False)

    def test_pass_exit_0(self):
        code, outcome = self._judge(["sh", "-c", "echo 'VERDICT: PASS' #"])
        self.assertEqual((code, outcome), (judge_mod.EXIT_PASS, "PASS"))

    def test_fail_exit_2(self):
        code, outcome = self._judge(["sh", "-c", "echo 'VERDICT: FAIL — bad' #"])
        self.assertEqual((code, outcome), (judge_mod.EXIT_FAIL, "FAIL"))

    def test_silence_exit_3(self):
        code, outcome = self._judge(["sh", "-c", "echo 'thinking...' #"])
        self.assertEqual((code, outcome), (judge_mod.EXIT_NOVERDICT, "NO VERDICT"))

    def test_timeout_exit_3(self):
        code, outcome = self._judge(["sh", "-c", "sleep 10 #"], timeout_s=1)
        self.assertEqual(code, judge_mod.EXIT_NOVERDICT)
        self.assertIn("TIMEOUT", outcome)

    def test_missing_judge_cli_exit_3(self):
        code, outcome = self._judge(["definitely-not-a-real-cli-xyz"])
        self.assertEqual(code, judge_mod.EXIT_NOVERDICT)

    def test_bad_workdir_exit_3(self):
        code, _ = judge_mod.judge(story="s", workdir="/nonexistent/dir/xyz",
                                  judge_cmd=["true"], echo=False)
        self.assertEqual(code, judge_mod.EXIT_NOVERDICT)

    def test_log_tee(self):
        with tempfile.TemporaryDirectory() as td:
            log = os.path.join(td, "judge.log")
            code, _ = judge_mod.judge(story="s", workdir=os.getcwd(),
                                      judge_cmd=["sh", "-c", "echo 'VERDICT: PASS' #"],
                                      log_path=log, echo=False)
            self.assertEqual(code, judge_mod.EXIT_PASS)
            with open(log) as fh:
                self.assertIn("VERDICT: PASS", fh.read())


class TestPromptAdvisoryWiring(unittest.TestCase):
    def test_advisory_is_marked_non_gating(self):
        p = judge_mod.build_prompt(story="S", workdir="/w",
                                   advisory="  [medium]\n    - a.ts:1 (x) y")
        self.assertIn("NON-GATING", p)
        self.assertIn("do NOT factor into the verdict", p.replace("They do NOT",
                                                                  "do NOT"))

    def test_no_advisory_block_when_absent(self):
        p = judge_mod.build_prompt(story="S", workdir="/w")
        self.assertNotIn("ADVISORY", p)


if __name__ == "__main__":
    unittest.main()
