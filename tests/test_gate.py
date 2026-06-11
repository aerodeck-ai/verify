"""Gate contract tests — exit codes 3/4/5/0 and the trivial-probe rejector.

The fixture-refusal cases here mirror the factory regression fixtures: a gate
that accepts an `echo done` probe, a `test -e` probe, or a `.*` EXPECT is a
gate that closes lies.
"""
import unittest

from aerodeck_verify import gate


class TestSentinels(unittest.TestCase):
    DESC = (
        "Some story text.\n"
        "### VERIFICATION-PROBE: curl -s http://localhost:1234/health\n"
        "### VERIFICATION-EXPECT: ^ok$\n"
    )

    def test_extract(self):
        self.assertEqual(gate.extract_sentinel(self.DESC, "VERIFICATION-PROBE"),
                         "curl -s http://localhost:1234/health")
        self.assertEqual(gate.extract_sentinel(self.DESC, "VERIFICATION-EXPECT"),
                         "^ok$")

    def test_extract_unheaded(self):
        desc = "VERIFICATION-PROBE: run-it\nVERIFICATION-EXPECT: yes"
        self.assertEqual(gate.extract_sentinel(desc, "VERIFICATION-PROBE"), "run-it")

    def test_missing(self):
        self.assertIsNone(gate.extract_sentinel("no sentinels here",
                                                "VERIFICATION-PROBE"))
        self.assertIsNone(gate.extract_sentinel(None, "VERIFICATION-PROBE"))


class TestTrivialProbeRejector(unittest.TestCase):
    def test_fabrication_rejected(self):
        for probe in ["echo done", "printf ok", "true", "yes", "cat file.txt",
                      ": nothing"]:
            self.assertTrue(gate.is_trivial_probe(probe), probe)

    def test_existence_rejected(self):
        for probe in ["test -e /tmp/x", "test -f /tmp/x", "ls /tmp",
                      "systemctl is-active myservice", "pgrep myproc",
                      "stat /tmp/x"]:
            self.assertTrue(gate.is_trivial_probe(probe), probe)

    def test_pipeline_literal_echo_rejected(self):
        # Fabricating the expected output at the end of a pipeline
        self.assertTrue(gate.is_trivial_probe("run-thing; echo ok"))
        self.assertTrue(gate.is_trivial_probe("run-thing && printf ok"))
        self.assertTrue(gate.is_trivial_probe("run-thing | yes"))

    def test_pipeline_computed_echo_allowed(self):
        # echo of COMPUTED values is legitimate result-surfacing
        self.assertFalse(gate.is_trivial_probe('rc=$(run-thing); echo "rc=$rc"'))

    def test_behavioural_allowed(self):
        for probe in ["curl -s http://localhost:1234/health",
                      "python3 -c 'import mymod; print(mymod.x)'",
                      "grep -c pattern /var/log/app.log"]:
            self.assertFalse(gate.is_trivial_probe(probe), probe)


class TestTautologicalExpect(unittest.TestCase):
    def test_tautologies_rejected(self):
        for expect in [".*", "^.*$", ".+", "", "^$"]:
            self.assertTrue(gate.is_tautological_expect(expect), expect)

    def test_real_expects_allowed(self):
        for expect in ["^ok$", "^verify$", "GATE CLOSED", r"^\d+ rows$"]:
            self.assertFalse(gate.is_tautological_expect(expect), expect)


class TestEvaluate(unittest.TestCase):
    def test_no_sentinels_exit_3(self):
        code, msgs = gate.evaluate(description="just prose, no sentinels")
        self.assertEqual(code, gate.EXIT_NO_SENTINELS)
        self.assertIn("fail-closed", msgs[0])

    def test_trivial_probe_exit_4(self):
        code, msgs = gate.evaluate(probe="echo done", expect="done")
        self.assertEqual(code, gate.EXIT_REJECTED)
        self.assertIn("not behavioural", msgs[0])

    def test_tautological_expect_exit_4(self):
        code, msgs = gate.evaluate(probe="curl -s http://x/health", expect=".*")
        self.assertEqual(code, gate.EXIT_REJECTED)
        self.assertIn("tautological", msgs[0])

    def test_invalid_regex_exit_4(self):
        code, msgs = gate.evaluate(probe="seq 3", expect="[unclosed")
        self.assertEqual(code, gate.EXIT_REJECTED)
        self.assertIn("not a valid regex", msgs[0])

    def test_mismatch_exit_5(self):
        code, msgs = gate.evaluate(probe="seq 3", expect="^banana$")
        self.assertEqual(code, gate.EXIT_MISMATCH)
        self.assertIn("close refused", msgs[0])

    def test_match_exit_0(self):
        code, msgs = gate.evaluate(probe="seq 3", expect=r"(^|\n)2(\n|$)")
        self.assertEqual(code, gate.EXIT_PASS)

    def test_probe_timeout_is_mismatch(self):
        code, _ = gate.evaluate(probe="sleep 5", expect="never", timeout_s=1)
        self.assertEqual(code, gate.EXIT_MISMATCH)

    def test_description_path(self):
        desc = ("### VERIFICATION-PROBE: seq 2\n"
                "### VERIFICATION-EXPECT: (^|\\n)2(\\n|$)\n")
        code, _ = gate.evaluate(description=desc)
        self.assertEqual(code, gate.EXIT_PASS)


if __name__ == "__main__":
    unittest.main()
