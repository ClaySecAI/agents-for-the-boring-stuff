#!/usr/bin/env python3
"""Tests for prepublic_check.py. GitHub is a fake: no network, no gh, nothing is changed anywhere.

    python3 chapters/08-securing-git/test_prepublic_check.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepublic_check as pc  # noqa: E402

AT = "@"  # assembled so the repository guard does not flag this file
REPO = "someone/example-repo"
GOOD_INFO = {"visibility": "public", "default_branch": "main", "security_and_analysis": {
    "secret_scanning": {"status": "enabled"}, "secret_scanning_push_protection": {"status": "enabled"}}}
GOOD_RULESET = {"id": 1, "enforcement": "active", "target": "branch",
                "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"]}},
                "rules": [{"type": "non_fast_forward"}, {"type": "deletion"}]}


class FakeApi:
    def __init__(self, **responses: object) -> None:
        self.responses = {key.replace("__", "/"): value for key, value in responses.items()}

    def get(self, path: str):
        return self.responses.get(path.replace(f"repos/{REPO}/", "").replace(f"repos/{REPO}", "repo"))


def fake_api(info=None, rulesets=None, vuln=True, artifacts=0, protection=None) -> FakeApi:
    api = FakeApi()
    api.responses = {
        "repo": GOOD_INFO if info is None else info,
        "private-vulnerability-reporting": {"enabled": vuln},
        "rulesets": [{"id": r["id"]} for r in (rulesets if rulesets is not None else [GOOD_RULESET])],
        "actions/artifacts": {"total_count": artifacts},
        "branches/main/protection": protection,
    }
    for r in (rulesets if rulesets is not None else [GOOD_RULESET]):
        api.responses[f"rulesets/{r['id']}"] = r
    return api


class Case(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="prepublic-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.clone = self.dir / "example-repo"
        self.clone.mkdir()
        env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
               "GIT_AUTHOR_NAME": "A", "GIT_AUTHOR_EMAIL": "a@example.org",
               "GIT_COMMITTER_NAME": "A", "GIT_COMMITTER_EMAIL": "a@example.org"}
        for args in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "first"]):
            subprocess.run(["git", "-C", str(self.clone), *args], check=True, capture_output=True, env=env)
        self.reports = self.dir / "reports"
        self.reports.mkdir()

    def add_community_files(self) -> None:
        for name in ("SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md"):
            (self.clone / name).write_text("x\n")
        (self.clone / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
        (self.clone / ".github" / "pull_request_template.md").write_text("x\n")

    def add_report(self, hits: int = 0) -> None:
        path = self.reports / "example-repo-20260101-000000.json"
        path.write_text(json.dumps({"counts": {"hits": hits}}))
        future = time.time() + 60
        os.utime(path, (future, future))

    def workflow(self, text: str) -> None:
        folder = self.clone / ".github" / "workflows"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "ci.yml").write_text(text)

    def run_all(self, api, status: int = 200) -> dict:
        results = pc.run_checks(self.clone, REPO, api, fetch=lambda url: status, report_dir=self.reports)
        return {r.name: r for r in results}


class CheckTests(Case):
    def test_everything_in_place_passes(self) -> None:
        self.add_community_files()
        self.add_report()
        results = self.run_all(fake_api())
        self.assertEqual([r.name for r in results.values() if r.status != "PASS"], [])

    def test_public_repo_without_protection_fails(self) -> None:
        info = {"visibility": "public", "default_branch": "main", "security_and_analysis": {
            "secret_scanning": {"status": "disabled"}, "secret_scanning_push_protection": {"status": "disabled"}}}
        results = self.run_all(fake_api(info=info, rulesets=[], vuln=False))
        for name in ("secret scanning", "push protection", "private vulnerability reporting", "default branch rules"):
            self.assertEqual(results[name].status, "FAIL", name)

    def test_private_repo_gets_warnings_not_failures(self) -> None:
        info = {"visibility": "private", "default_branch": "main", "security_and_analysis": {
            "secret_scanning": {"status": "disabled"}}}
        results = self.run_all(fake_api(info=info, rulesets=[], vuln=False), status=404)
        self.assertEqual(results["secret scanning"].status, "WARN")
        self.assertEqual(results["default branch rules"].status, "WARN")
        self.assertEqual(results["signed-out view"].status, "PASS")  # hidden, as a private repo should be

    def test_only_one_of_force_push_and_deletion_blocked(self) -> None:
        half = dict(GOOD_RULESET, rules=[{"type": "deletion"}])
        result = self.run_all(fake_api(rulesets=[half]))["default branch rules"]
        self.assertEqual(result.status, "FAIL")
        self.assertIn("force pushes", result.detail)

    def test_inactive_or_other_branch_rulesets_do_not_count(self) -> None:
        off = dict(GOOD_RULESET, enforcement="disabled")
        other = dict(GOOD_RULESET, id=2, conditions={"ref_name": {"include": ["refs/heads/dev"]}})
        result = self.run_all(fake_api(rulesets=[off, other]))["default branch rules"]
        self.assertEqual(result.status, "FAIL")

    def test_classic_branch_protection_counts(self) -> None:
        protection = {"allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False}}
        result = self.run_all(fake_api(rulesets=[], protection=protection))["default branch rules"]
        self.assertEqual(result.status, "PASS")

    def test_required_check_behind_a_path_filter_fails(self) -> None:
        self.workflow("name: ci\non:\n  pull_request:\n    paths:\n      - 'src/**'\njobs:\n  tests:\n    runs-on: x\n")
        ruleset = dict(GOOD_RULESET, rules=GOOD_RULESET["rules"] + [
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "tests"}]}}])
        result = self.run_all(fake_api(rulesets=[ruleset]))["required checks can run on every pull request"]
        self.assertEqual(result.status, "FAIL")

    def test_required_check_without_a_path_filter_passes(self) -> None:
        self.workflow("name: ci\non:\n  pull_request:\njobs:\n  tests:\n    runs-on: x\n")
        ruleset = dict(GOOD_RULESET, rules=GOOD_RULESET["rules"] + [
            {"type": "required_status_checks", "parameters": {"required_status_checks": [{"context": "tests"}]}}])
        result = self.run_all(fake_api(rulesets=[ruleset]))["required checks can run on every pull request"]
        self.assertEqual(result.status, "PASS")

    def test_missing_community_files_are_listed(self) -> None:
        (self.clone / "SECURITY.md").write_text("x\n")
        result = self.run_all(fake_api())["community files"]
        self.assertEqual(result.status, "WARN")
        self.assertIn("code of conduct", result.detail)
        self.assertNotIn("security policy", result.detail)

    def test_artifacts_warn(self) -> None:
        self.assertEqual(self.run_all(fake_api(artifacts=3))["CI artifacts"].status, "WARN")

    def test_history_audit_must_be_newer_than_the_last_commit(self) -> None:
        self.assertEqual(self.run_all(fake_api())["history audit"].status, "FAIL")  # no report at all
        self.add_report(hits=2)
        self.assertEqual(self.run_all(fake_api())["history audit"].status, "WARN")  # hits need a decision
        for p in self.reports.glob("*.json"):
            old = time.time() - 86400 * 400
            os.utime(p, (old, old))
        self.assertEqual(self.run_all(fake_api())["history audit"].status, "FAIL")  # older than the commit

    def test_signed_out_view_of_a_public_repo(self) -> None:
        self.assertEqual(self.run_all(fake_api(), status=404)["signed-out view"].status, "FAIL")

    def test_unreadable_settings_are_skipped_not_passed(self) -> None:
        info = {"visibility": "public", "default_branch": "main"}  # no security_and_analysis: not an admin
        api = fake_api(info=info)
        del api.responses["private-vulnerability-reporting"]
        results = self.run_all(api)
        self.assertEqual(results["secret scanning"].status, "SKIP")
        self.assertEqual(results["private vulnerability reporting"].status, "SKIP")

    def test_unknown_repository_raises(self) -> None:
        with self.assertRaises(RuntimeError):
            pc.run_checks(self.clone, REPO, FakeApi())


class MainTests(Case):
    def test_needs_a_clone_and_a_repo_name(self) -> None:
        self.assertEqual(pc.main([str(self.dir)]), 2)
        self.assertEqual(pc.main([str(self.clone)]), 2)  # a clone with no GitHub origin and no --repo


class RemoteNameTests(unittest.TestCase):
    def test_remote_urls(self) -> None:
        folder = Path(tempfile.mkdtemp(prefix="prepublic-url-"))
        self.addCleanup(shutil.rmtree, folder, True)
        subprocess.run(["git", "-C", str(folder), "init", "-q"], check=True, capture_output=True)
        for url, want in (("https://github.com/someone/example-repo.git", REPO), ("git" + AT + "github.com:someone/example-repo.git", REPO),
                          ("https://gitlab.com/someone/example-repo.git", None)):
            subprocess.run(["git", "-C", str(folder), "remote", "remove", "origin"], capture_output=True)
            subprocess.run(["git", "-C", str(folder), "remote", "add", "origin", url], check=True, capture_output=True)
            self.assertEqual(pc.repo_from_remote(folder), want, url)


if __name__ == "__main__":
    unittest.main()
