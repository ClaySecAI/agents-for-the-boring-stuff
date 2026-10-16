"""Tests for check_repo_clean.py: plant each kind of leak and make sure it is blocked.

    python3 scripts/test_check_repo_clean.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "scripts" / "check_repo_clean.py"


class GuardTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name) / "repo"
        # A copy of this very repo, so "the real repo passes" is tested on real files.
        shutil.copytree(REPO, self.dir, ignore=shutil.ignore_patterns(".git", "__pycache__"))
        self.git("init", "-q")

    def tearDown(self):
        self._tmp.cleanup()

    def git(self, *args: str):
        return subprocess.run(["git", *args], cwd=self.dir, capture_output=True, text=True)

    def guard(self, mode: str):
        return subprocess.run([sys.executable, "-B", str(self.dir / "scripts" / "check_repo_clean.py"), mode],
                              cwd=self.dir, capture_output=True, text=True)

    def stage_and_check(self, relpath: str, content: bytes | str, force: bool = False):
        target = self.dir / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content if isinstance(content, bytes) else content.encode())
        self.git("add", *(["-f"] if force else []), relpath)
        return self.guard("--staged")

    def assertBlocked(self, result, *fragments: str):
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        for fragment in fragments:
            self.assertIn(fragment, result.stdout)

    def test_this_repo_as_it_stands_is_clean(self):
        result = self.guard("--all")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_force_added_practice_file_is_blocked(self):
        self.assertBlocked(self.stage_and_check("chapters/01-files-and-folders/practice/downloads/note.md", "hi", force=True),
                           "practice folder")

    def test_generated_labels_and_plans_are_blocked_even_when_forced(self):
        self.assertBlocked(self.stage_and_check("classification.json", "{}", force=True), "generated output")
        self.assertBlocked(self.stage_and_check("organize-plan.md", "| a | b |", force=True), "generated output")

    def test_binary_files_are_blocked(self):
        self.assertBlocked(self.stage_and_check("extract_text", b"\x00\x01\x02", force=True),
                           "not on the allowlist", "binary")

    def test_unlisted_file_types_are_blocked(self):
        self.assertBlocked(self.stage_and_check("notes.pdf", "x"), "not on the allowlist")

    def test_home_directory_path_is_blocked_without_echoing_it(self):
        result = self.stage_and_check("docs.md", "see /Users/someone/Documents/secret")
        self.assertBlocked(result, "docs.md: line 1 contains a home-directory path")
        self.assertNotIn("someone", result.stdout)

    def test_email_address_is_blocked(self):
        self.assertBlocked(self.stage_and_check("docs.md", "mail me at person@gmail.com"), "an email address")

    def test_example_addresses_are_allowed(self):
        self.assertEqual(self.stage_and_check("docs.md", "write to someone@example.com").returncode, 0)

    def test_ssn_shaped_number_is_blocked(self):
        self.assertBlocked(self.stage_and_check("docs.md", "ID 123-45-6789"), "an SSN-shaped number")

    def test_api_key_is_blocked(self):
        self.assertBlocked(self.stage_and_check("docs.md", "key = sk-" + "a" * 30), "an API key or token")

    def test_private_blocklist_term_is_blocked_case_insensitively(self):
        (self.dir / ".git" / "private-terms.txt").write_text("# my terms\nJane Q Example\n")
        result = self.stage_and_check("docs.md", "written by jane q example")
        self.assertBlocked(result, "private blocklist")
        self.assertNotIn("jane", result.stdout.lower())

    def test_oversized_file_is_blocked(self):
        self.assertBlocked(self.stage_and_check("big.md", "x" * (300 * 1024)), "KB (limit")

    def test_innocent_change_passes(self):
        self.assertEqual(self.stage_and_check("docs.md", "# A harmless page\nNothing personal here.\n").returncode, 0)

    def test_hook_is_executable_and_runs_the_guard(self):
        hook = self.dir / ".githooks" / "pre-commit"
        self.assertTrue(hook.exists())
        self.git("config", "core.hooksPath", ".githooks")
        self.git("add", "-A")
        self.git("add", "-f", "-N", ".")  # nothing sneaky; just make the tree visible
        (self.dir / "leak.md").write_text("person@gmail.com")
        self.git("add", "leak.md")
        done = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com",
                               "commit", "-q", "-m", "should be refused"],
                              cwd=self.dir, capture_output=True, text=True)
        self.assertNotEqual(done.returncode, 0, "the pre-commit hook should have refused this commit")
        self.assertIn("BLOCKED", done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
