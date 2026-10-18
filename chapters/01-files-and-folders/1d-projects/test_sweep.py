"""Tests for sweep.py. A small fake model server stands in for LM Studio, so no model is needed, and a fake
`lms` command stands in for LM Studio's, so no real model is loaded or unloaded.

    python3 test_sweep.py
"""
from __future__ import annotations

import argparse
import contextlib
import http.server
import io
import itertools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep  # noqa: E402

PROJECTS = [{"name": "Taxes", "description": "tax forms"}, {"name": "Workouts", "description": "training"}]


class FakeModel(http.server.BaseHTTPRequestHandler):
    """Answers by file name: 'tax' -> Taxes, 'key' -> Taxes but credentials, 'mystery' -> Unsorted, else Workouts.
    Like LM Studio, it answers 404 for a model it does not have."""

    accepted = {sweep.DEFAULTS["model"]}
    asked: list = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeModel.asked.append(body["model"])
        if body["model"] not in FakeModel.accepted:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error": "model not found"}')
            return
        user = body["messages"][-1]["content"]
        name = user.split("File name: ", 1)[1].splitlines()[0].lower()
        if "mystery" in name:
            answer = {"primary": "Unsorted", "also": [], "sensitivity": "none"}
        elif "key" in name:
            answer = {"primary": "Taxes", "also": [], "sensitivity": "credentials"}
        elif "tax" in name:
            answer = {"primary": "Taxes", "also": [], "sensitivity": "financial"}
        else:
            answer = {"primary": "Workouts", "also": [], "sensitivity": "none"}
        payload = json.dumps({"choices": [{"message": {"content": json.dumps(answer)}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), FakeModel)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.server.server_address[1]}/v1"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeModel.accepted = {sweep.DEFAULTS["model"]}
        FakeModel.asked = []
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / "Downloads"
        self.folder.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        (self.state / "projects.json").write_text(json.dumps(PROJECTS))
        (self.folder / "Taxes").mkdir()
        (self.folder / "Workouts").mkdir()
        (self.folder / "Workouts" / "old-run.txt").write_text("already filed")
        self.config(max_moves=100)

    def tearDown(self):
        self._tmp.cleanup()

    def config(self, **extra):
        cfg = {"folder": str(self.folder), "state_dir": str(self.state), "base_url": self.url,
               "manage_model": False, "min_age_minutes": 60, "min_battery_percent": 0, **extra}
        (self.state / "config.json").write_text(json.dumps(cfg))

    def add(self, name, text="content", age_hours=5):
        path = self.folder / name
        path.write_text(text)
        old = time.time() - age_hours * 3600
        os.utime(path, (old, old))

    def sweep(self, *args, env=None, config=None):
        env = {**os.environ, "SWEEP_NO_NOTIFY": "1", **(env or {})}
        config = config or self.state / "config.json"
        return subprocess.run([sys.executable, "-B", str(HERE / "sweep.py"), *args, "--config", str(config)],
                              capture_output=True, text=True, env=env)

    def listing(self, folder=None):
        folder = folder or self.folder
        return sorted(str(p.relative_to(folder)) for p in folder.rglob("*"))

    def fake_lms(self):
        """A fake `lms` first on PATH that logs its arguments. The real one would unload the reader's models."""
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        log = self.root / "lms.log"
        lms = bin_dir / "lms"
        lms.write_text(f'#!/bin/sh\necho "$@" >> "{log}"\n')
        lms.chmod(0o755)
        path = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        self.assertEqual(shutil.which("lms", path=path), str(lms))
        return {"PATH": path}, log


class PureTests(Base):
    def test_eligible_skips_what_a_sweep_must_not_touch(self):
        self.add("fresh.pdf", age_hours=0)
        self.add("report.pdf")
        self.add("movie.crdownload")
        self.add(".hidden")
        self.add("empty.txt", text="")
        files, skipped = sweep.eligible(self.folder, 60)
        self.assertEqual(files, ["report.pdf"])
        self.assertEqual((skipped["recent"], skipped["partial"], skipped["hidden"], skipped["empty"]), (1, 1, 1, 1))
        self.assertEqual(skipped["not_a_file"], 2)          # the two project folders

    def test_decide_holds_sensitive_and_unsorted_files(self):
        assigned = {"a": {"primary": "Taxes", "sensitivity": "financial"},
                    "b": {"primary": "Taxes", "sensitivity": "credentials"},
                    "c": {"primary": "Unsorted", "sensitivity": "none"},
                    "d": {"primary": "Not a project", "sensitivity": "none"},
                    "e": {"primary": "Workouts"}}
        moves, held = sweep.decide(assigned, ["Taxes", "Workouts"], ["credentials", "unknown"])
        self.assertEqual(moves, {"a": "Taxes"})
        self.assertEqual(held, {"unsorted": 2, "sensitive": 2})

    def test_a_destination_is_never_an_existing_file(self):
        (self.folder / "Workouts" / "run.txt").write_text("x")
        dests = sweep.destinations(self.folder, {"run.txt": "Workouts", "other.txt": "Workouts"})
        self.assertEqual(dests["run.txt"], "Workouts/run (2).txt")
        self.assertEqual(dests["other.txt"], "Workouts/other.txt")

    def test_power_rules(self):
        ac = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t23%; charging; 1:00 remaining present: true"
        low = "Now drawing from 'Battery Power'\n -InternalBattery-0 (id=1)\t42%; discharging; 3:00 remaining present: true"
        high = low.replace("42%", "81%")
        self.assertTrue(sweep.power_ok(ac, 50)[0])                 # plugged in: always
        self.assertFalse(sweep.power_ok(low, 50)[0])
        self.assertTrue(sweep.power_ok(high, 50)[0])
        self.assertTrue(sweep.power_ok("", 50)[0])                 # a desktop has no battery
        self.assertTrue(sweep.power_ok(low, 0)[0])

    def test_a_low_battery_skips_without_leaving_a_report(self):
        if sys.platform != "darwin":
            self.skipTest("pmset is macOS only")
        pm = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
        if "Battery Power" not in pm:
            self.skipTest("this Mac is on AC power or has no battery")
        self.config(min_battery_percent=101)                         # impossible to satisfy on battery
        self.add("tax-form.pdf")
        done = self.sweep("run")
        self.assertIn("Skipped", done.stdout)
        self.assertEqual(list((self.state / "runs").glob("*/report.json")) if (self.state / "runs").exists() else [], [])


class RunTests(Base):
    def test_a_sweep_files_new_loose_files_into_existing_folders_and_leaves_everything_else(self):
        self.add("tax-form.pdf")
        self.add("morning-run.txt")
        self.add("my-key.pem")                    # credentials: held
        self.add("mystery.bin")                   # unsorted: held
        self.add("fresh.txt", age_hours=0)        # too new: skipped
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        after = self.listing()
        self.assertIn("Taxes/tax-form.pdf", after)
        self.assertIn("Workouts/morning-run.txt", after)
        self.assertIn("Workouts/old-run.txt", after)
        for stays in ("my-key.pem", "mystery.bin", "fresh.txt"):
            self.assertIn(stays, after)
        self.assertEqual(len(after), len(before))                         # nothing created or lost
        report = json.loads(next((self.state / "runs").glob("*/report.json")).read_text())
        self.assertEqual((report["moved"], report["held"]["sensitive"], report["held"]["unsorted"]), (2, 1, 1))
        self.assertNotIn("tax-form", json.dumps(report))                   # the report holds counts, not names

    def test_undo_puts_the_files_back(self):
        self.add("tax-form.pdf")
        self.add("morning-run.txt")
        before = self.listing()
        self.assertEqual(self.sweep("run").returncode, 0)
        self.assertNotEqual(self.listing(), before)
        undone = self.sweep("undo")
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual(self.listing(), before)

    def test_a_dry_run_moves_nothing(self):
        self.add("tax-form.pdf")
        before = self.listing()
        done = self.sweep("run", "--dry-run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("dry run", done.stdout)
        self.assertEqual(self.listing(), before)

    def test_too_many_moves_stops_the_sweep_with_nothing_moved(self):
        self.config(max_moves=2)
        for i in range(3):
            self.add(f"run-{i}.txt")
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 1)
        self.assertIn("over the limit", done.stdout)
        self.assertEqual(self.listing(), before)

    def test_no_model_server_stops_quietly(self):
        self.config(base_url="http://127.0.0.1:9/v1")
        self.add("tax-form.pdf")
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 1)
        self.assertEqual(self.listing(), before)

    def test_a_second_sweep_with_nothing_new_does_nothing(self):
        self.add("tax-form.pdf")
        self.assertEqual(self.sweep("run").returncode, 0)
        again = self.sweep("run")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertIn("nothing new", again.stdout)

    def test_a_folder_rule_moves_the_whole_folder_into_a_project_and_undo_restores_it(self):
        photos = self.folder / "Event Photos 123"
        photos.mkdir()
        (photos / "img1.jpg").write_text("p1")
        old = time.time() - 86400
        os.utime(photos, (old, old))
        (self.folder / "Misc stuff").mkdir()
        self.config(folder_rules={"Event Photos 123": {"unit": "Workouts"}})
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Workouts/Event Photos 123/img1.jpg", self.listing())
        self.assertNotIn("Event Photos 123", self.listing())
        report = json.loads(next((self.state / "runs").glob("*/report.json")).read_text())
        self.assertEqual((report["folders_by_rule"], report["untracked_folders"]), (1, 1))
        self.assertEqual(self.sweep("undo").returncode, 0)
        self.assertEqual(self.listing(), before)

    def test_untracked_folders_are_listed_not_touched(self):
        (self.folder / "Misc stuff").mkdir()
        listed = self.sweep("folders")
        self.assertIn("Misc stuff", listed.stdout)
        self.assertNotIn("Taxes", listed.stdout.split("rule:")[1])

    def test_the_agent_plist_checks_daily_and_at_login_but_sweeps_weekly(self):
        import plistlib
        plist = plistlib.loads(self.sweep("agent").stdout.encode())
        self.assertEqual(plist["StartCalendarInterval"], {"Hour": 3, "Minute": 0})
        self.assertTrue(plist["RunAtLoad"])
        args = plist["ProgramArguments"]
        self.assertEqual(args[2:5], ["run", "--if-due", "7"])
        self.assertIn(str((self.state / "config.json").resolve()), args)

    def test_if_due_skips_a_recent_sweep_and_runs_after_a_week(self):
        self.add("tax-form.pdf")
        self.assertEqual(self.sweep("run").returncode, 0)
        self.add("morning-run.txt")
        skipped = self.sweep("run", "--if-due", "7")
        self.assertIn("Not due", skipped.stdout)
        self.assertIn("morning-run.txt", self.listing())           # still loose: nothing ran
        report = next((self.state / "runs").glob("*/report.json"))
        old = report.parent.with_name("2020-01-01-030000-000")
        report.parent.rename(old)                                   # pretend the last sweep was years ago
        ran = self.sweep("run", "--if-due", "7")
        self.assertNotIn("Not due", ran.stdout)
        self.assertIn("Workouts/morning-run.txt", self.listing())

    def test_a_dry_run_or_a_stopped_sweep_does_not_count_as_the_last_sweep(self):
        for name, data in (("2026-10-01-030000-000", {"dry_run": True}), ("2026-10-02-030000-000", {"stopped": "x"})):
            d = self.state / "runs" / name
            d.mkdir(parents=True)
            (d / "report.json").write_text(json.dumps(data))
        runs = sorted((self.state / "runs").iterdir())
        self.assertIsNone(sweep.days_since_last_sweep(runs))

    def test_an_unmanaged_server_is_asked_for_the_configured_model(self):
        FakeModel.accepted = {"phi4"}                               # e.g. Ollama, which knows nothing of "sweep"
        self.config(model="phi4")
        self.add("tax-form.pdf")
        done = self.sweep("run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Taxes/tax-form.pdf", self.listing())
        self.assertEqual(set(FakeModel.asked), {"phi4"})

    def test_a_managed_model_is_loaded_and_unloaded_under_its_own_name(self):
        env, log = self.fake_lms()
        FakeModel.accepted = {"sweep"}
        self.config(manage_model=True)
        self.add("tax-form.pdf")
        done = self.sweep("run", env=env)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Taxes/tax-form.pdf", self.listing())
        self.assertEqual(set(FakeModel.asked), {"sweep"})
        calls = log.read_text().splitlines()
        self.assertIn(f"load {sweep.DEFAULTS['model']} -y --identifier sweep --context-length 6144", calls)
        self.assertEqual(calls[-1], "unload sweep")
        self.assertFalse([c for c in calls if "--all" in c])          # the reader's own models stay loaded

    def test_a_sweep_in_which_every_request_fails_is_stopped_and_not_counted(self):
        self.config(model="not-loaded")
        self.add("tax-form.pdf")
        self.add("morning-run.txt")
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
        self.assertIn("answered none of the 2 files", done.stdout)
        self.assertEqual(self.listing(), before)
        self.assertIsNone(sweep.days_since_last_sweep(sorted((self.state / "runs").iterdir())))

    def test_a_pipe_in_a_file_name_does_not_block_the_sweep(self):
        self.add("tax return | 2025.pdf")                       # browsers' "Save as PDF" titles often have one
        self.add("run | notes.txt", age_hours=0)                # too new: left in place, but still a plan row
        before = self.listing()
        done = self.sweep("run")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Taxes/tax return | 2025.pdf", self.listing())
        self.assertIn("run | notes.txt", self.listing())
        self.assertEqual(self.sweep("undo").returncode, 0)
        self.assertEqual(self.listing(), before)

    def test_an_undone_sweep_does_not_count_as_the_last_sweep(self):
        self.add("tax-form.pdf")
        self.assertEqual(self.sweep("run").returncode, 0)
        self.assertEqual(self.sweep("undo").returncode, 0)
        again = self.sweep("run", "--if-due", "7")
        self.assertNotIn("Not due", again.stdout)
        self.assertIn("Taxes/tax-form.pdf", self.listing())


class InitTests(Base):
    def init(self, folder, practice):
        home = self.root / "home"
        home.mkdir(exist_ok=True)
        done = self.sweep("init", str(folder), config=practice / "config.json", env={"HOME": str(home)})
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse((home / "Library").exists())                # nothing in the real state folder
        return done

    def test_a_practice_config_keeps_its_runs_beside_it(self):
        practice = self.root / "practice"
        self.init(self.folder, practice)
        cfg = json.loads((practice / "config.json").read_text())
        self.assertEqual(Path(cfg["state_dir"]), practice.resolve())
        self.assertEqual(cfg["projects_root"], "")
        names = [p["name"] for p in json.loads((practice / "projects.json").read_text())]
        self.assertEqual(names, ["Taxes", "Workouts"])

    def test_init_keeps_a_project_list_that_is_already_there(self):
        practice = self.root / "practice"
        practice.mkdir()
        (practice / "projects.json").write_text(json.dumps(PROJECTS[:1]))
        self.assertIn("Kept", self.init(self.folder, practice).stdout)
        self.assertEqual(json.loads((practice / "projects.json").read_text()), PROJECTS[:1])

    def test_a_folder_sorted_into_Projects_is_swept_into_the_folders_inside_it(self):
        sorted_folder = self.root / "Sorted"                         # Chapter 1D's default layout
        for name in ("Taxes", "Workouts", "_Unsorted"):
            (sorted_folder / "Projects" / name).mkdir(parents=True)
            (sorted_folder / "Projects" / name / "filed-by-1d.txt").write_text("already filed")
        practice = self.root / "practice"
        self.init(sorted_folder, practice)
        names = [p["name"] for p in json.loads((practice / "projects.json").read_text())]
        self.assertEqual(names, ["Taxes", "Workouts"])               # not one project named "Projects"
        config = practice / "config.json"
        cfg = json.loads(config.read_text())
        self.assertEqual(cfg["projects_root"], "Projects")
        config.write_text(json.dumps({**cfg, "base_url": self.url, "manage_model": False, "min_battery_percent": 0}))
        path = sorted_folder / "tax-form.pdf"
        path.write_text("content")
        old = time.time() - 5 * 3600
        os.utime(path, (old, old))
        before = self.listing(sorted_folder)
        done = self.sweep("run", config=config)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("Projects/Taxes/tax-form.pdf", self.listing(sorted_folder))
        self.assertIn("0 folder(s)", self.sweep("folders", config=config).stdout)
        self.assertEqual(self.sweep("undo", config=config).returncode, 0)
        self.assertEqual(self.listing(sorted_folder), before)


class VerificationTests(Base):
    """A moved file that hashes differently undoes the sweep. Run in-process so the hash can be made to change."""

    def run_in_process(self):
        args = argparse.Namespace(config=self.state / "config.json", dry_run=False, if_due=None)
        out = io.StringIO()
        hashes = itertools.count()
        with mock.patch.dict(os.environ, {"SWEEP_NO_NOTIFY": "1"}), contextlib.redirect_stdout(out), \
                mock.patch.object(sweep, "sha", lambda path: str(next(hashes))):  # every file reads as changed
            code = sweep.cmd_run(args)
        return code, out.getvalue()

    def test_a_changed_file_undoes_the_whole_sweep(self):
        self.add("tax-form.pdf")
        self.add("morning-run.txt")
        before = self.listing()
        code, out = self.run_in_process()
        self.assertEqual(code, 2)
        self.assertIn("sweep undone", out)
        self.assertEqual(self.listing(), before)

    def test_an_undo_that_is_refused_is_reported_with_the_command_that_finishes_it(self):
        self.add("tax-form.pdf")
        before = self.listing()
        real = sweep.run_script

        def run_script(script, *args, env=None):
            if script.endswith("undo_plan.py"):            # a new download with the same name arrived meanwhile
                (self.folder / "tax-form.pdf").write_text("newer")
            return real(script, *args, env=env)

        with mock.patch.object(sweep, "run_script", run_script):
            code, out = self.run_in_process()
        self.assertEqual(code, 2)
        run_id = next((self.state / "runs").iterdir()).name
        self.assertIn(f"undo refused, run: sweep.py undo {run_id}", out)
        (self.folder / "tax-form.pdf").unlink()
        undone = self.sweep("undo", run_id)
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual(self.listing(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
