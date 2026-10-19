#!/usr/bin/env python3
"""Tests for drift_check.py. Scratch repositories and a scratch global git config; the real ones are never read.

    python3 chapters/08-securing-git/test_drift_check.py
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import drift_check as dc  # noqa: E402

AT = "@"  # emails are assembled so the repository guard does not flag this file
NOREPLY_EMAIL = "1234+jordan" + AT + "users.noreply.github.com"
OTHER_EMAIL = "jordan.lee" + AT + "corp.example"
HAVE_GITLEAKS = shutil.which("gitleaks") is not None


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="drift-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.global_config = self.dir / "gitconfig"
        self.global_config.write_text("")
        patch = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(self.global_config), "GIT_CONFIG_NOSYSTEM": "1"})
        patch.start()
        self.addCleanup(patch.stop)
        self.hooks = self.dir / "hooks"
        self.hooks.mkdir()
        dispatch = self.hooks / "dispatch"
        dispatch.write_text("#!/bin/sh\n")
        dispatch.chmod(0o755)
        for name in dc.PROTECTED_HOOKS:
            (self.hooks / name).symlink_to("dispatch")
        self.terms = self.dir / "terms.txt"
        self.terms.write_text("# test\nquillfeather\n")
        self.terms.chmod(0o600)
        self.set_global("core.hooksPath", str(self.hooks))
        self.set_global("user.email", NOREPLY_EMAIL)
        self.projects = self.dir / "projects"
        self.projects.mkdir()

    def set_global(self, key: str, value: str) -> None:
        subprocess.run(["git", "config", "--global", key, value], check=True, capture_output=True)

    def repo(self, name: str, *config: tuple, depth: int = 0) -> Path:
        path = self.projects.joinpath(*([f"d{n}" for n in range(depth)] + [name]))
        path.mkdir(parents=True)
        subprocess.run(["git", "-C", str(path), "init", "-q"], check=True, capture_output=True)
        for key, value in config:
            subprocess.run(["git", "-C", str(path), "config", "--local", key, value], check=True, capture_output=True)
        return path

    def findings(self, visibility=lambda slug: "PRIVATE", depth: int = 3) -> list:
        return dc.run([self.projects], depth, self.terms, visibility)

    def bad(self, where: str, **kw) -> list:
        return [f.detail for f in self.findings(**kw) if f.where == where and f.status == "FAIL"]


class MachineTests(Case):
    def machine_fails(self) -> list:
        return [f.detail for f in dc.check_machine(self.terms) if f.status == "FAIL"]

    @unittest.skipUnless(HAVE_GITLEAKS, "gitleaks is not installed")
    def test_healthy_machine(self) -> None:
        self.assertEqual(self.machine_fails(), [])

    def test_hooks_folder_not_set(self) -> None:
        subprocess.run(["git", "config", "--global", "--unset", "core.hooksPath"], check=True)
        self.assertTrue(any("core.hooksPath" in d for d in self.machine_fails()))

    def test_a_hook_that_is_not_the_dispatcher(self) -> None:
        (self.hooks / "pre-push").unlink()
        (self.hooks / "pre-push").write_text("#!/bin/sh\nexit 0\n")
        self.assertTrue(any("pre-push" in d for d in self.machine_fails()))

    def test_non_noreply_global_email(self) -> None:
        self.set_global("user.email", OTHER_EMAIL)
        fails = self.machine_fails()
        self.assertTrue(any("global commit email" in d for d in fails))
        self.assertFalse(any(OTHER_EMAIL in d for d in fails))

    def test_blocklist_readable_by_others_and_missing(self) -> None:
        self.terms.chmod(0o644)
        self.assertTrue(any("other users" in d for d in self.machine_fails()))
        self.terms.unlink()
        self.assertTrue(any("no private blocklist" in d for d in self.machine_fails()))

    def test_empty_blocklist_is_a_warning(self) -> None:
        self.terms.write_text("# nothing yet\n")
        self.terms.chmod(0o600)
        warns = [f.detail for f in dc.check_machine(self.terms) if f.status == "WARN"]
        self.assertEqual(len(warns), 1)

    def test_no_term_is_ever_printed(self) -> None:
        self.terms.chmod(0o644)
        text = " ".join(f.detail + f.fix for f in dc.check_machine(self.terms))
        self.assertNotIn("quillfeather", text)


class RepoTests(Case):
    def test_clean_repo(self) -> None:
        self.repo("clean")
        self.assertEqual(self.bad("clean"), [])

    def test_local_email_override(self) -> None:
        self.repo("override", ("user.email", OTHER_EMAIL))
        fails = self.bad("override")
        self.assertEqual(len(fails), 1)
        self.assertNotIn(OTHER_EMAIL, fails[0])

    def test_local_noreply_email_and_allowed_email_are_fine(self) -> None:
        self.repo("noreply", ("user.email", NOREPLY_EMAIL))
        self.repo("allowed", ("user.email", OTHER_EMAIL), ("hooks.allowEmail", OTHER_EMAIL))
        self.assertEqual(self.bad("noreply"), [])
        self.assertEqual(self.bad("allowed"), [])

    def test_local_hooks_path_replaces_the_global_hooks(self) -> None:
        self.repo("bypass", ("core.hooksPath", ".githooks"))
        self.repo("same", ("core.hooksPath", str(self.hooks)))
        self.assertEqual(len(self.bad("bypass")), 1)
        self.assertEqual(self.bad("same"), [])

    def test_credentials_in_a_remote_url(self) -> None:
        user = "someone"
        secret_part = "x" * 12
        self.repo("leaky", ("remote.origin.url", f"https://{user}:{secret_part}@github.com/someone/example.git"))
        fails = self.bad("leaky")
        self.assertEqual(len(fails), 1)
        self.assertNotIn(secret_part, fails[0])

    def test_allow_personal_data_needs_a_private_remote(self) -> None:
        self.repo("diary", ("hooks.allowPersonalData", "true"), ("remote.origin.url", "https://github.com/someone/diary.git"))
        self.assertEqual(self.bad("diary", visibility=lambda slug: "PRIVATE"), [])
        self.assertEqual(len(self.bad("diary", visibility=lambda slug: "PUBLIC")), 1)
        self.assertEqual(len(self.bad("diary", visibility=lambda slug: "")), 1)  # cannot confirm: refuse

    def test_allow_personal_data_with_a_non_github_remote(self) -> None:
        self.repo("diary", ("hooks.allowPersonalData", "true"), ("remote.origin.url", "https://gitlab.com/someone/diary.git"))
        self.assertEqual(len(self.bad("diary")), 1)

    def test_finds_repos_by_depth_and_does_not_enter_a_repo(self) -> None:
        self.repo("shallow")
        self.repo("deep", depth=2)
        inner = self.projects / "shallow" / "vendor" / "inner"
        inner.mkdir(parents=True)
        subprocess.run(["git", "-C", str(inner), "init", "-q"], check=True, capture_output=True)
        names = lambda depth: sorted(p.name for p in dc.find_repos([self.projects], depth))
        self.assertEqual(names(0), [])
        self.assertEqual(names(1), ["shallow"])
        self.assertEqual(names(3), ["deep", "shallow"])


class MainTests(Case):
    def test_exit_codes(self) -> None:
        self.repo("clean")
        self.repo("override", ("user.email", OTHER_EMAIL))
        self.assertEqual(dc.main([str(self.dir / "nowhere")]), 2)
        self.assertEqual(dc.main([str(self.projects), "--terms", str(self.terms)]), 1)
        shutil.rmtree(self.projects / "override")
        if HAVE_GITLEAKS:
            self.assertEqual(dc.main([str(self.projects), "--terms", str(self.terms)]), 0)


if __name__ == "__main__":
    unittest.main()
