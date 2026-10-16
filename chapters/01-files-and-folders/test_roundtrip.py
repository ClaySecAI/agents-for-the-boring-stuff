"""Tests for plan -> apply -> verify -> undo. No model needed: labels are faked by rule.

    python3 test_roundtrip.py

verify.py only compares content hashes, so it proves nothing was lost, not that paths were
restored. The round-trip tests therefore also diff a full before/after listing of the folder.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CATEGORY = {".jpg": "Images", ".png": "Images", ".pdf": "Documents", ".docx": "Documents",
            ".xlsx": "Spreadsheets", ".csv": "Spreadsheets", ".dmg": "Installers",
            ".pkg": "Installers", ".zip": "Archives", ".gz": "Archives", ".txt": "Text"}


def run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(HERE / script), *map(str, args)],
                          capture_output=True, text=True)


def listing(folder: Path) -> list[str]:
    """Every file AND directory, so an undo that leaves stray empty folders is caught."""
    return sorted(str(p.relative_to(folder)) + ("/" if p.is_dir() else "") for p in folder.rglob("*"))


def fake_labels(folder: Path, top_level: bool) -> dict:
    paths = folder.iterdir() if top_level else folder.rglob("*")
    labels = {}
    for p in paths:
        if p.is_file():
            kind = "financial" if p.suffix == ".pdf" else "none"
            labels[str(p.relative_to(folder))] = {"category": CATEGORY.get(p.suffix, "Review"),
                                                  "sensitivity": kind}
    return labels


class Base(unittest.TestCase):
    top_level = False
    with_project = False

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / "downloads"
        args = [self.folder] + (["--with-project"] if self.with_project else [])
        self.assertEqual(run("make_mess.py", *args).returncode, 0)
        self.before = listing(self.folder)
        run("verify.py", "snapshot", self.folder)
        (self.root / "labels.json").write_text(json.dumps(fake_labels(self.folder, self.top_level)))
        flags = ["--top-level"] if self.top_level else []
        made = run("make_plan.py", *flags, self.root / "labels.json", self.folder)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.plan = self.root / "organize-plan.md"

    def tearDown(self):
        self._tmp.cleanup()

    def apply(self):
        return run("apply_plan.py", self.plan, self.folder)

    def check(self):
        return run("apply_plan.py", "--check", self.plan, self.folder)

    def undo(self, *flags):
        return run("undo_plan.py", *flags, self.folder)

    def verify(self):
        return run("verify.py", "check", self.folder)


class RecursiveRoundTrip(Base):
    def test_apply_verify_undo_restores_every_path(self):
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        applied = self.apply()
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        self.assertIn("PASS", self.verify().stdout)
        self.assertNotEqual(listing(self.folder), self.before)
        undone = self.undo()
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(listing(self.folder), self.before)  # same files, same folders, nothing extra

    def test_undo_twice_is_refused_and_changes_nothing(self):
        self.apply()
        self.undo()
        again = self.undo()
        self.assertEqual(again.returncode, 1)
        self.assertIn("Nothing to undo", again.stdout + again.stderr)
        self.assertEqual(listing(self.folder), self.before)

    def test_second_apply_refused_while_first_is_on_record(self):
        self.apply()
        second = self.apply()
        self.assertEqual(second.returncode, 1)
        self.assertIn("earlier applied plan", second.stdout)

    def test_undo_refuses_when_a_moved_file_is_gone(self):
        self.apply()
        victim = next(p for p in self.folder.rglob("*.csv"))
        victim.unlink()
        self.assertEqual(self.undo("--check").returncode, 1)
        self.assertIn("gone from both", self.undo("--check").stdout)

    def test_undo_refuses_to_overwrite_something_now_at_the_original_spot(self):
        self.apply()
        (self.folder / "todo.txt").write_text("a new file that took the old name")
        refused = self.undo()
        self.assertEqual(refused.returncode, 1)
        self.assertIn("refusing to overwrite", refused.stdout)

    def test_finder_dsstore_does_not_break_verify_or_checks(self):
        (self.folder / ".DS_Store").write_bytes(b"finder junk")
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self.apply()
        (self.folder / "Images" / ".DS_Store").write_bytes(b"more finder junk")
        self.assertIn("PASS", self.verify().stdout)

    def test_skipping_a_file_is_rejected(self):
        lines = self.plan.read_text().splitlines()
        victim = next(i for i, line in enumerate(lines) if line.startswith("| todo.txt"))
        del lines[victim]
        self.plan.write_text("\n".join(lines) + "\n")
        rejected = self.check()
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("plan skips this item: todo.txt", rejected.stdout)


class TopLevelRoundTrip(Base):
    top_level = True
    with_project = True

    def test_subfolders_move_as_units_and_come_back(self):
        text = self.plan.read_text()
        self.assertIn("Mode: top-level", text)
        self.assertIn("| some-project | Folders/some-project |", text)
        self.assertNotIn("some-project/src", text)  # the inside of a project is never listed
        project_before = listing(self.folder / "some-project")
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self.assertEqual(self.apply().returncode, 0)
        self.assertEqual(listing(self.folder / "Folders" / "some-project"), project_before)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(self.undo().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(listing(self.folder), self.before)  # `Folders/` is gone again

    def test_view_for_claude_has_no_folder_names_or_counts(self):
        view = (self.root / "claude-view.txt").read_text()
        self.assertNotIn("some-project", view)
        self.assertNotIn("old_stuff", view)
        self.assertIn("(dir)", view)

    def test_mode_line_removed_is_rejected(self):
        self.plan.write_text(self.plan.read_text().replace("Mode: top-level\n", ""))
        rejected = self.check()
        self.assertEqual(rejected.returncode, 1)  # recursive mode sees files the plan never listed

    def test_recursive_plan_relabelled_top_level_is_rejected(self):
        recursive_folder = self.root / "other"
        run("make_mess.py", recursive_folder)
        (self.root / "l2.json").write_text(json.dumps(fake_labels(recursive_folder, False)))
        run("make_plan.py", "--out-dir", self.root / "plan2", self.root / "l2.json", recursive_folder)
        plan2 = self.root / "plan2" / "organize-plan.md"
        text = plan2.read_text().replace("| From | To | Why |", "Mode: top-level\n\n| From | To | Why |", 1)
        plan2.write_text(text)
        rejected = run("apply_plan.py", "--check", plan2, recursive_folder)
        self.assertEqual(rejected.returncode, 1)
        self.assertIn("nested path", rejected.stdout)

    def test_left_in_place_row_keeps_the_folder_and_survives_undo(self):
        self.plan.write_text(self.plan.read_text().replace(
            "| some-project | Folders/some-project |", "| some-project | some-project |"))
        self.assertEqual(self.apply().returncode, 0)
        self.assertTrue((self.folder / "some-project" / "src" / "app.py").exists())
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), self.before)

    def test_preexisting_folder_named_like_a_category_is_left_alone(self):
        (self.folder / "Documents").mkdir()
        (self.folder / "Documents" / "mine.txt").write_text("my own folder")
        before = listing(self.folder)
        (self.root / "labels.json").write_text(json.dumps(fake_labels(self.folder, True)))
        run("make_plan.py", "--top-level", self.root / "labels.json", self.folder)
        self.assertIn("| Documents | Documents |", self.plan.read_text())
        self.assertEqual(self.apply().returncode, 0)
        self.assertTrue((self.folder / "Documents" / "mine.txt").exists())
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
