"""Tests for build_quick_reference.py.  python3 scripts/test_build_quick_reference.py"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_quick_reference as q  # noqa: E402


class QuickReferenceTests(unittest.TestCase):
    def test_extracts_only_the_common_tasks_section(self):
        text = "# Title\n\n## Intro\nx\n\n## Common tasks\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## Exercises\n1. y\n"
        self.assertEqual(q.common_tasks(text), "| a | b |\n|---|---|\n| 1 | 2 |")
        self.assertIsNone(q.common_tasks("# T\n\n## Exercises\n"))

    def test_every_chapter_with_a_table_appears_in_the_built_file(self):
        built = q.build()
        for path in q.chapter_files():
            if q.common_tasks(path.read_text()):
                self.assertIn(f"({path.relative_to(q.ROOT)})", built)

    def test_the_checked_in_file_is_current(self):
        out = q.ROOT / "QUICK-REFERENCE.md"
        self.assertTrue(out.exists() and out.read_text() == q.build(), "run scripts/build_quick_reference.py")


if __name__ == "__main__":
    unittest.main()
