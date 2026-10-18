"""Tests for plan -> apply -> verify -> undo. No model needed: labels are faked by rule.

    python3 test_roundtrip.py

verify.py only compares content hashes, so it proves nothing was lost, not that paths were
restored. The round-trip tests therefore also diff a full before/after listing of the folder.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.dont_write_bytecode = True  # the in-process imports below must not leave __pycache__ in the chapter
sys.path.insert(0, str(HERE))
import apply_plan  # noqa: E402
from plan_common import parse_plan  # noqa: E402

os.environ.pop("PLAN_STATE_DIR", None)  # a value from your shell would send the test records elsewhere
CATEGORY = {".jpg": "Images", ".png": "Images", ".pdf": "Documents", ".docx": "Documents",
            ".xlsx": "Spreadsheets", ".csv": "Spreadsheets", ".dmg": "Installers",
            ".pkg": "Installers", ".zip": "Archives", ".gz": "Archives", ".txt": "Text"}


def run(script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(HERE / script), *map(str, args)],
                          capture_output=True, text=True, cwd=cwd)


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
        self.plan = self.root / "organize-plan.md"
        self.replan()

    def tearDown(self):
        self._tmp.cleanup()

    def replan(self):
        """Take the "before" listing and snapshot, label the files, and make the plan. Run it again after a
        test adds something to the fixture."""
        self.before = listing(self.folder)
        run("verify.py", "snapshot", self.folder)
        (self.root / "labels.json").write_text(json.dumps(fake_labels(self.folder, self.top_level)))
        flags = ["--top-level"] if self.top_level else []
        made = run("make_plan.py", *flags, self.root / "labels.json", self.folder)
        self.assertEqual(made.returncode, 0, made.stderr)

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

    def test_finder_bookkeeping_inside_a_created_folder_does_not_stop_it_being_removed(self):
        self.apply()
        for created in ("Images", "Documents"):
            (self.folder / created / ".DS_Store").write_bytes(b"finder looked at this folder")
        undone = self.undo()
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual(listing(self.folder), self.before)  # no leftover folders, no stray .DS_Store

    def test_a_real_file_inside_a_created_folder_is_never_deleted(self):
        self.apply()
        (self.folder / "Images" / "ADDED_LATER.txt").write_text("someone put this here after the move")
        self.undo()
        self.assertTrue((self.folder / "Images" / "ADDED_LATER.txt").is_file())  # the folder is kept

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

    def test_names_that_differ_only_in_case_get_separate_destinations(self):
        # Both land in one folder under names a Mac treats as the same, so one used to overwrite the other.
        (self.folder / "Invoice.pdf").write_text("[pretend PDF] the newer invoice")
        (self.folder / "old_stuff" / "invoice.pdf").write_text("[pretend PDF] the older invoice")
        self.replan()
        moves = dict(parse_plan(self.plan.read_text())[1])
        self.assertNotEqual(moves["Invoice.pdf"].casefold(), moves["old_stuff/invoice.pdf"].casefold())
        self.assertEqual(self.apply().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), self.before)

    def test_undo_keeps_a_folder_that_was_there_before_apply(self):
        (self.folder / "Images").mkdir()  # holds no file, so no plan row mentions it
        (self.folder / "Images" / ".DS_Store").write_bytes(b"finder looked at this folder")
        self.replan()
        self.assertEqual(self.apply().returncode, 0)
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), self.before)  # Images/ and its .DS_Store are still there

    def test_a_link_stays_where_it_is_and_undo_still_works(self):
        os.symlink("todo.txt", self.folder / "todo-shortcut.txt")  # its target is a file the plan moves
        os.symlink("nowhere.txt", self.folder / "broken-link")
        self.replan()
        self.assertIn("| todo-shortcut.txt | todo-shortcut.txt |", self.plan.read_text())
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self.assertEqual(self.apply().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(self.undo().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(listing(self.folder), self.before)
        self.assertEqual((self.folder / "todo-shortcut.txt").read_text(), (self.folder / "todo.txt").read_text())

    def test_check_reports_an_applied_plan_still_on_record(self):
        self.apply()
        checked = self.check()
        self.assertEqual(checked.returncode, 1)
        self.assertIn("earlier applied plan", checked.stdout)
        self.assertIn(str(self.root.resolve() / ".downloads.applied-plan.md"), checked.stdout)


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

    def test_folder_named_like_a_category_in_lower_case_is_left_alone(self):
        (self.folder / "documents").mkdir()
        (self.folder / "documents" / "mine.txt").write_text("my own folder")
        self.replan()
        self.assertIn("| documents | documents |", self.plan.read_text())
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self.assertEqual(self.apply().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), self.before)

    def test_links_stay_where_they_are(self):
        os.symlink("old_stuff", self.folder / "old-stuff-link")  # a link to a folder the plan moves
        os.symlink("nowhere.txt", self.folder / "broken-link")
        self.replan()
        text = self.plan.read_text()
        self.assertIn("| old-stuff-link | old-stuff-link |", text)
        self.assertIn("| broken-link | broken-link |", text)
        self.assertEqual(self.check().returncode, 0, self.check().stdout)
        self.assertEqual(self.apply().returncode, 0)
        self.assertIn("PASS", self.verify().stdout)
        self.assertEqual(self.undo().returncode, 0)
        self.assertEqual(listing(self.folder), self.before)


class HandWrittenPlans(unittest.TestCase):
    """Plans that make_plan.py never writes but an agent or a person might, on a two-file folder."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()  # the records are named from the resolved path
        self.folder = self.root / "small"
        self.folder.mkdir()
        (self.folder / "a.txt").write_text("alpha")
        (self.folder / "b.txt").write_text("bravo")
        self.record = self.root / ".small.applied-plan.md"

    def plan(self, *rows: str) -> Path:
        path = self.root / "plan.md"
        path.write_text("| From | To | Why |\n|---|---|---|\n" + "".join(f"| {row} | test |\n" for row in rows))
        return path

    def check(self, *rows: str) -> subprocess.CompletedProcess:
        return run("apply_plan.py", "--check", self.plan(*rows), self.folder)

    def locked(self, name: str) -> Path:
        """A folder inside the test folder that nothing can be moved into."""
        if os.geteuid() == 0:
            self.skipTest("root ignores folder permissions")
        path = self.folder / name
        path.mkdir()
        path.chmod(0o555)
        self.addCleanup(path.chmod, 0o755)
        return path

    def test_destinations_that_differ_only_in_case_are_rejected(self):
        checked = self.check("a.txt | Docs/Note.txt", "b.txt | Docs/note.txt")
        self.assertEqual(checked.returncode, 1)
        self.assertIn("same destination", checked.stdout)

    def test_apply_stops_rather_than_overwrite_when_the_check_missed_something(self):
        plan = self.plan("a.txt | b.txt", "b.txt | b.txt")
        out = io.StringIO()
        with unittest.mock.patch.object(apply_plan, "preflight", return_value=[]), \
                contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as stopped:
            apply_plan.main(plan, self.folder, False)
        self.assertEqual(stopped.exception.code, 1)
        self.assertIn("interrupted", out.getvalue())
        self.assertIn("undo_plan.py", out.getvalue())
        self.assertEqual((self.folder / "a.txt").read_text(), "alpha")
        self.assertEqual((self.folder / "b.txt").read_text(), "bravo")

    def test_paths_that_leave_the_folder_are_rejected(self):
        (self.root / "outside.txt").write_text("not part of the folder")
        (self.root / "elsewhere").mkdir()
        os.symlink("../elsewhere", self.folder / "linked")
        cases = {
            "To goes up": ("a.txt | ../escaped/a.txt", "b.txt | b.txt"),
            "To is absolute": (f"a.txt | {self.root}/escaped/a.txt", "b.txt | b.txt"),
            "From goes up": ("../outside.txt | Text/outside.txt", "a.txt | a.txt", "b.txt | b.txt"),
            "To is the folder itself": ("a.txt | .", "b.txt | b.txt"),
            "To goes through a link": ("a.txt | linked/a.txt", "b.txt | b.txt"),
        }
        for case, rows in cases.items():
            with self.subTest(case):
                checked = self.check(*rows)
                self.assertEqual(checked.returncode, 1, checked.stdout)
                self.assertIn("leaves the folder", checked.stdout)

    def test_undo_rejects_paths_that_leave_the_folder(self):
        (self.root / "outside.txt").write_text("not part of the folder")
        plan = self.plan("a.txt | a.txt", "b.txt | b.txt", "pulled-in.txt | ../outside.txt")
        undone = run("undo_plan.py", plan, self.folder)
        self.assertEqual(undone.returncode, 1)
        self.assertIn("leaves the folder", undone.stdout)
        self.assertTrue((self.root / "outside.txt").is_file())

    def test_a_destination_that_another_row_uses_as_a_folder_is_rejected(self):
        for rows in (("b.txt | Docs/b.txt", "a.txt | Docs"),
                     ("a.txt | Docs", "b.txt | Docs/b.txt"),
                     ("b.txt | Docs/b.txt", "a.txt | docs")):
            with self.subTest(rows=rows):
                checked = self.check(*rows)
                self.assertEqual(checked.returncode, 1, checked.stdout)
                self.assertIn("also a folder", checked.stdout)

    def test_a_link_is_never_moved(self):
        os.symlink("a.txt", self.folder / "a-link.txt")
        checked = self.check("a.txt | a.txt", "b.txt | b.txt", "a-link.txt | Links/a-link.txt")
        self.assertEqual(checked.returncode, 1)
        self.assertIn("cannot be moved", checked.stdout)

    def test_undo_puts_back_a_link_that_stopped_working_when_it_moved(self):
        # The state an apply without the link check left: the link moved, its target did not.
        (self.folder / "Links").mkdir()
        os.symlink("a.txt", self.folder / "Links" / "a-link.txt")
        undone = run("undo_plan.py", self.plan("a.txt | a.txt", "b.txt | b.txt", "a-link.txt | Links/a-link.txt"),
                     self.folder)
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual((self.folder / "a-link.txt").read_text(), "alpha")

    def test_dot_as_the_folder_names_the_records_after_the_real_folder(self):
        plan = self.plan("a.txt | Text/a.txt", "b.txt | Text/b.txt")
        self.assertEqual(run("verify.py", "snapshot", ".", cwd=self.folder).returncode, 0)
        self.assertEqual(run("apply_plan.py", plan, ".", cwd=self.folder).returncode, 0)
        self.assertEqual(sorted(p.name for p in self.root.iterdir() if p.name.startswith(".")),
                         [".small.applied-plan.md", ".small.manifest.json"])
        self.assertIn("PASS", run("verify.py", "check", ".", cwd=self.folder).stdout)
        self.assertEqual(run("undo_plan.py", ".", cwd=self.folder).returncode, 0)

    def test_a_failed_first_move_leaves_a_record_that_undo_retires(self):
        self.locked("Locked")
        plan = self.plan("a.txt | Locked/a.txt", "b.txt | b.txt")
        applied = run("apply_plan.py", plan, self.folder)
        self.assertEqual(applied.returncode, 1)
        self.assertIn("interrupted", applied.stdout)
        self.assertIn("undo_plan.py", applied.stdout)
        self.assertTrue((self.folder / "a.txt").is_file())  # nothing moved
        self.assertIn(str(self.record), run("apply_plan.py", "--check", plan, self.folder).stdout)
        undone = run("undo_plan.py", self.folder)
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertFalse(self.record.exists())  # retired, so the plan can be applied again
        self.assertEqual(run("apply_plan.py", "--check", plan, self.folder).returncode, 0)

    def test_an_apply_interrupted_partway_can_be_undone(self):
        self.locked("Locked")
        before = listing(self.folder)
        applied = run("apply_plan.py", self.plan("a.txt | Open/a.txt", "b.txt | Locked/b.txt"), self.folder)
        self.assertEqual(applied.returncode, 1)
        self.assertIn("interrupted after 1 of 2", applied.stdout)
        undone = run("undo_plan.py", self.folder)
        self.assertEqual(undone.returncode, 0, undone.stdout + undone.stderr)
        self.assertEqual(listing(self.folder), before)  # Open/ is gone; Locked/ was there before and stays


class CommandLineTests(unittest.TestCase):
    def test_help_prints_usage_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            for script in ("make_mess.py", "apply_plan.py", "undo_plan.py"):
                with self.subTest(script=script):
                    helped = run(script, "--help", cwd=Path(tmp))
                    self.assertEqual(helped.returncode, 0, helped.stdout + helped.stderr)
                    self.assertIn(script, helped.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])  # make_mess.py did not build practice/downloads

    def test_every_script_has_the_annotations_import(self):
        # Without it, Python 3.9 cannot read an annotation such as `Path | None`.
        for script in sorted(HERE.glob("*.py")):
            with self.subTest(script=script.name):
                self.assertIn("from __future__ import annotations", script.read_text())

    def test_skill_stops_instead_of_moving_files_by_hand(self):
        skill = (HERE.parent.parent / ".claude" / "skills" / "organize-folder" / "SKILL.md").read_text()
        self.assertNotIn("`mv` each file yourself", skill)


class StateDirTests(unittest.TestCase):
    def test_records_go_to_plan_state_dir_when_set_and_undo_finds_them(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder, state = root / "synced" / "Downloads", root / "state"
            folder.mkdir(parents=True)
            state.mkdir()
            (folder / "a.txt").write_text("one")
            (folder / "b.txt").write_text("two")
            plan = root / "plan.md"
            plan.write_text("Mode: top-level\n\n| From | To | Why |\n|---|---|---|\n"
                            "| a.txt | Group/a.txt | x |\n| b.txt | Group/b.txt | x |\n")
            env = {**os.environ, "PLAN_STATE_DIR": str(state)}

            def go(script, *args):
                return subprocess.run([sys.executable, "-B", str(HERE / script), *map(str, args)],
                                      capture_output=True, text=True, env=env)
            self.assertEqual(go("verify.py", "snapshot", folder).returncode, 0)
            self.assertEqual(go("apply_plan.py", plan, folder).returncode, 0)
            self.assertEqual(go("verify.py", "check", folder).returncode, 0)
            beside = sorted(p.name for p in folder.parent.iterdir())
            self.assertEqual(beside, ["Downloads"])                      # nothing hidden next to the synced folder
            self.assertTrue(list(state.glob(".*applied-plan.md")) and list(state.glob(".*manifest.json")))
            self.assertEqual(go("undo_plan.py", folder).returncode, 0)
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["a.txt", "b.txt"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
