"""Tests for style_check.py.  python3 scripts/test_style_check.py"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import style_check as sc  # noqa: E402


def rules(text, chapter=False):
    return {rule for _, _, rule, _ in sc.check_text(text, "t.md", chapter)}


class StyleTests(unittest.TestCase):
    def test_clean_prose_passes(self):
        self.assertEqual(rules("# A short heading\n\nRun the script. It prints the counts, then stops.\n"), set())

    def test_catches_the_usual_patterns(self):
        text = ("# Why Agents Matter Most Today\n\nThis is a robust system — it truly helps. Moreover, files, folders and links work.\n\n"
                "**Note.** A bold lead-in.\n\n- **Label.** text\n")
        self.assertEqual(rules(text), {"title-case-heading", "inflated-word", "em-dash", "filler", "serial-comma?", "bold-lead-in", "list-label-period"})

    def test_code_blocks_are_skipped(self):
        self.assertEqual(rules("```\nthis is robust — and comprehensive\n```\n"), set())

    def test_the_off_switch_skips_quoted_examples(self):
        self.assertEqual(rules("<!-- style:off -->\nrobust — truly\n<!-- style:on -->\n"), set())

    def test_a_label_with_a_colon_is_fine(self):
        self.assertEqual(rules("- **Label:** text\n"), set())

    def test_long_paragraphs_are_flagged(self):
        self.assertIn("long-paragraph", rules("word " * 140 + "\n"))

    def test_british_spellings_are_flagged_but_american_ones_are_not(self):
        self.assertEqual(rules("The labelled file and a neighbouring folder.\n"), {"british-spelling"})
        self.assertEqual(rules("The labeled file, a realistic test, a specialist, and a neighboring folder.\n"), set())

    def test_chapters_need_common_tasks_and_exercises(self):
        self.assertEqual(rules("# Chapter\n\ntext\n", chapter=True), {"missing-section"})
        self.assertEqual(rules("# Chapter\n\n## 1.9 Limits\n\n## What we tested\n\n## Common tasks\n\n## Exercises\n", chapter=True), set())


if __name__ == "__main__":
    unittest.main()
