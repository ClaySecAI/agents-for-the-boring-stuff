"""Tests for verify_editor_ledger.py.  python3 scripts/test_verify_editor_ledger.py"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import verify_editor_ledger as v  # noqa: E402

CATALOG = "# A\n\n## Middle\n\n## Return to the output contract\n\ntext\n"
GOOD = ("Edited the file.\n\nLedger\nSkill loaded: yes\nCatalog read through: Return to the output contract\n"
        "Linter findings: 6 -> 0\nEditing passes: 1\nModel-only checks: none\n")


class LedgerTests(unittest.TestCase):
    def test_a_correct_ledger_passes(self):
        self.assertEqual(v.verify(GOOD, CATALOG), [])

    def test_no_ledger_fails(self):
        self.assertEqual(v.verify("I edited it.", CATALOG), ["no Ledger block"])

    def test_stopping_early_is_caught_by_the_wrong_last_heading(self):
        early = GOOD.replace("Return to the output contract", "Middle")
        self.assertTrue(any("last heading" in p for p in v.verify(early, CATALOG)))

    def test_a_failure_does_not_print_the_expected_heading(self):
        early = GOOD.replace("Return to the output contract", "Middle")
        self.assertNotIn("Return to the output contract", " ".join(v.verify(early, CATALOG)))

    def test_help_prints_usage_and_exits_zero(self):
        done = subprocess.run([sys.executable, str(Path(v.__file__)), "--help"], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0)
        self.assertIn("verify_editor_ledger.py <report.txt>", done.stdout)

    def test_skill_not_loaded_fails(self):
        self.assertTrue(v.verify(GOOD.replace("yes", "no", 1), CATALOG))

    def test_the_real_catalog_has_a_last_heading(self):
        self.assertTrue(v.last_heading(v.CATALOG.read_text()))


if __name__ == "__main__":
    unittest.main()
