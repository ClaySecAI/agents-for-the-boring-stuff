#!/usr/bin/env python3
"""Tests for example_personal_data_check.py. Scratch repositories, a scratch git configuration, an invented blocklist.

    python3 chapters/08-securing-git/test_example_personal_data_check.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / "example_personal_data_check.py"
AT = "@"  # emails are assembled so the repository guard does not flag this file
NOREPLY = "1234+jordan" + AT + "users.noreply.github.com"
OTHER = "jordan.lee" + AT + "corp.example"


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="pdcheck-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.home = self.dir / "home"
        self.home.mkdir()
        self.repo = self.dir / "repo"
        self.repo.mkdir()
        self.terms = self.dir / "terms.txt"
        self.terms.write_text("# test\nquillfeather\n")
        self.env = {**os.environ, "HOME": str(self.home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        self.git("init", "-q")
        self.git("config", "user.email", NOREPLY)

    def git(self, *args: str) -> None:
        subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, env=self.env)

    def stage(self, text: str, name: str = "notes.txt") -> None:
        (self.repo / name).write_text(text)
        self.git("add", name)

    def run_check(self, *extra: str):
        return subprocess.run([sys.executable, str(SCRIPT), "--terms", str(self.terms), *extra], cwd=self.repo,
                              capture_output=True, text=True, env=self.env)


class CheckTests(Case):
    def test_clean_change_passes(self) -> None:
        self.stage("nothing personal here\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_blocklist_term_is_found_and_never_printed(self) -> None:
        self.stage("one\ntwo quillfeather three\n")
        done = self.run_check()
        self.assertEqual(done.returncode, 1)
        self.assertIn("notes.txt:2", done.stdout)
        self.assertNotIn("quillfeather", done.stdout + done.stderr)

    def test_term_matches_whole_words_only(self) -> None:
        self.stage("quillfeathers and unquillfeather\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_term_match_ignores_case(self) -> None:
        self.stage("QuillFeather\n")
        self.assertEqual(self.run_check().returncode, 1)

    def test_only_added_lines_count(self) -> None:
        self.stage("keep quillfeather\n")
        self.git("-c", "user.name=A", "commit", "-q", "--no-verify", "-m", "x")
        self.stage("keep quillfeather\nnew clean line\n")
        done = self.run_check()
        self.assertEqual(done.returncode, 0)  # the old line is not part of this commit

    def test_home_path_is_found_and_not_printed(self) -> None:
        self.stage(f"path = {self.home}/project\n")
        done = self.run_check()
        self.assertEqual(done.returncode, 1)
        self.assertIn("home folder", done.stdout)
        self.assertNotIn(str(self.home), done.stdout)

    def test_non_noreply_email_is_refused_and_not_printed(self) -> None:
        self.git("config", "user.email", OTHER)
        self.stage("clean\n")
        done = self.run_check()
        self.assertEqual(done.returncode, 1)
        self.assertNotIn(OTHER, done.stdout + done.stderr)

    def test_allow_email_names_one_exception(self) -> None:
        self.git("config", "user.email", OTHER)
        self.git("config", "hooks.allowEmail", OTHER)
        self.stage("clean\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_missing_blocklist_still_checks_the_rest(self) -> None:
        self.terms.unlink()
        self.stage(f"path = {self.home}/x\n")
        self.assertEqual(self.run_check().returncode, 1)

    def test_outside_a_repository_exits_2(self) -> None:
        done = subprocess.run([sys.executable, str(SCRIPT), "--terms", str(self.terms)], cwd=self.dir,
                              capture_output=True, text=True, env={**self.env, "GIT_CEILING_DIRECTORIES": str(self.dir.parent)})
        self.assertEqual(done.returncode, 2)


if __name__ == "__main__":
    unittest.main()
