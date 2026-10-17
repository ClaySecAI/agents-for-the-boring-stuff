"""Tests for sweep.py. A small fake model server stands in for LM Studio, so no model is needed.

    python3 test_sweep.py
"""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sweep  # noqa: E402

PROJECTS = [{"name": "Taxes", "description": "tax forms"}, {"name": "Workouts", "description": "training"}]


class FakeModel(http.server.BaseHTTPRequestHandler):
    """Answers by file name: 'tax' -> Taxes, 'key' -> Taxes but credentials, 'mystery' -> Unsorted, else Workouts."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'{"data": []}')

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
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
               "manage_model": False, "min_age_minutes": 60, **extra}
        (self.state / "config.json").write_text(json.dumps(cfg))

    def add(self, name, text="content", age_hours=5):
        path = self.folder / name
        path.write_text(text)
        old = time.time() - age_hours * 3600
        os.utime(path, (old, old))

    def sweep(self, *args):
        env = {**os.environ, "SWEEP_NO_NOTIFY": "1"}
        return subprocess.run([sys.executable, "-B", str(HERE / "sweep.py"), *args, "--config", str(self.state / "config.json")],
                              capture_output=True, text=True, env=env)

    def listing(self):
        return sorted(str(p.relative_to(self.folder)) for p in self.folder.rglob("*"))


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

    def test_the_agent_plist_runs_weekly_and_names_the_config(self):
        import plistlib
        plist = plistlib.loads(self.sweep("agent").stdout.encode())
        self.assertEqual(plist["StartCalendarInterval"]["Weekday"], 0)
        self.assertIn(str((self.state / "config.json").resolve()), plist["ProgramArguments"])
        self.assertEqual(plist["ProgramArguments"][2], "run")


if __name__ == "__main__":
    unittest.main(verbosity=2)
