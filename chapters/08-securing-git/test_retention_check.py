#!/usr/bin/env python3
"""Tests for retention_check.py. GitHub is a fake: no network, nothing is changed anywhere.

    python3 chapters/08-securing-git/test_retention_check.py
"""
from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import retention_check as rc  # noqa: E402


class FakeApi:
    def __init__(self, days: dict, archived=(), refuse=(), unreadable=()) -> None:
        self.days = dict(days)
        self.archived = set(archived)
        self.refuse = set(refuse)  # setting is accepted by the fake but does not stick
        self.unreadable = set(unreadable)
        self.sets: list = []

    def whoami(self):
        return "someone"

    def repos(self, owner):
        return [{"name": n, "isArchived": n in self.archived, "isFork": False} for n in self.days]

    def get_days(self, owner, name):
        return None if name in self.unreadable else self.days[name]

    def set_days(self, owner, name, days):
        self.sets.append((name, days))
        if name not in self.refuse:
            self.days[name] = days
            self.unreadable.discard(name)
        return name not in self.unreadable

    def run(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = rc.main(list(argv), api=self)
        return code, out.getvalue()


class CheckTests(unittest.TestCase):
    def test_all_at_target_is_ok(self) -> None:
        api = FakeApi({"a": 7, "b": 7})
        code, out = api.run()
        self.assertEqual(code, 0)
        self.assertIn("2 at 7 days", out)

    def test_report_only_changes_nothing(self) -> None:
        api = FakeApi({"a": 7, "b": 90})
        code, out = api.run()
        self.assertEqual(code, 1)
        self.assertEqual(api.sets, [])
        self.assertIn("DIFFERS b: retention is 90 days, target 7", out)
        self.assertIn("--apply", out)

    def test_apply_sets_only_the_ones_that_differ_and_reads_back(self) -> None:
        api = FakeApi({"a": 7, "b": 90, "c": 30})
        code, out = api.run("--apply")
        self.assertEqual(code, 0)
        self.assertEqual(sorted(api.sets), [("b", 7), ("c", 7)])
        self.assertEqual(api.days, {"a": 7, "b": 7, "c": 7})
        self.assertIn("2 fixed", out)

    def test_a_setting_that_does_not_stick_fails(self) -> None:
        api = FakeApi({"a": 90}, refuse={"a"})
        code, out = api.run("--apply")
        self.assertEqual(code, 1)
        self.assertIn("FAIL    a", out)

    def test_unreadable_setting_is_not_passed(self) -> None:
        api = FakeApi({"a": 7}, unreadable={"a"})
        code, out = api.run()
        self.assertEqual(code, 1)
        self.assertIn("could not be read", out)

    def test_archived_repositories_are_skipped(self) -> None:
        api = FakeApi({"a": 90}, archived={"a"})
        code, out = api.run("--apply")
        self.assertEqual(code, 0)
        self.assertEqual(api.sets, [])
        self.assertIn("1 skipped", out)

    def test_custom_target(self) -> None:
        api = FakeApi({"a": 7})
        self.assertEqual(api.run("--days", "14")[0], 1)

    def test_days_outside_the_public_limit_are_refused(self) -> None:
        api = FakeApi({"a": 7})
        self.assertEqual(api.run("--days", "0")[0], 2)
        self.assertEqual(api.run("--days", "91")[0], 2)

    def test_cannot_list_repositories(self) -> None:
        api = FakeApi({"a": 7})
        api.repos = lambda owner: None
        self.assertEqual(api.run()[0], 2)

    def test_unknown_owner(self) -> None:
        api = FakeApi({"a": 7})
        api.whoami = lambda: None
        self.assertEqual(api.run()[0], 2)
        self.assertEqual(api.run("--owner", "someone")[0], 0)


if __name__ == "__main__":
    unittest.main()
