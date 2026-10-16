"""Tests for the project-based pipeline. No model needed: assignments are built from the answer key.

    python3 test_projects.py
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(HERE))
import assign_projects as assign  # noqa: E402
import score as scoring  # noqa: E402
import tag_files  # noqa: E402

ON_MAC = sys.platform == "darwin"


def run(script: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(script), *map(str, args)], capture_output=True, text=True)


def listing(folder: Path) -> list[str]:
    return sorted(str(p.relative_to(folder)) + ("/" if p.is_dir() else "") for p in folder.rglob("*"))


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.folder = self.root / "downloads"
        made = run(HERE / "make_project_mess.py", self.folder)
        self.assertEqual(made.returncode, 0, made.stderr)
        self.truth = json.loads((self.root / "truth.json").read_text())
        self.projects = self.root / "projects.json"
        self.names = [p["name"] for p in json.loads(self.projects.read_text())]
        self.assigned = {f: {"primary": t["primary"], "also": t["also"],
                             "sensitivity": "financial" if f.endswith(".pdf") else "none"}
                         for f, t in self.truth.items()}
        self.before = listing(self.folder)

    def tearDown(self):
        self._tmp.cleanup()

    def plan(self, *flags):
        (self.root / "assignments.json").write_text(json.dumps(self.assigned))
        done = run(HERE / "plan_projects.py", *flags, self.root / "assignments.json", self.projects, self.folder)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return (self.root / "organize-plan.md").read_text()


class PlanTests(Base):
    def test_files_go_to_their_project_and_also_column_lists_extra_projects(self):
        text = self.plan()
        self.assertIn("| From | To | Why | Also |", text)
        self.assertIn("| maplestone_quote_v2.pdf | Projects/Kitchen remodel/maplestone_quote_v2.pdf |", text)
        row = next(line for line in text.splitlines() if line.startswith("| buyers_order.pdf"))
        self.assertIn("Projects/Car purchase/buyers_order.pdf", row)
        self.assertTrue(row.rstrip().endswith("| Tax prep |"))
        self.assertIn("| untitled.txt | Projects/_Unsorted/untitled.txt |", text)

    def test_full_round_trip_with_chapter_1_scripts(self):
        run(CH1 / "verify.py", "snapshot", self.folder)
        plan = self.root / "organize-plan.md"
        self.plan()
        self.assertEqual(run(CH1 / "apply_plan.py", "--check", plan, self.folder).returncode, 0)
        self.assertEqual(run(CH1 / "apply_plan.py", plan, self.folder).returncode, 0)
        self.assertIn("PASS", run(CH1 / "verify.py", "check", self.folder).stdout)
        self.assertTrue((self.folder / "Projects" / "Tax prep" / "w2_2025.pdf").is_file())
        self.assertFalse((self.folder / "w2_2025.pdf").exists())
        self.assertEqual(run(CH1 / "undo_plan.py", self.folder).returncode, 0)
        self.assertIn("PASS", run(CH1 / "verify.py", "check", self.folder).stdout)
        self.assertEqual(listing(self.folder), self.before)

    def test_what_claude_may_see_has_no_names(self):
        self.plan()
        view = (self.root / "claude-view.txt").read_text()
        for project in self.names:
            self.assertNotIn(project, view)
        for filename in self.truth:
            self.assertNotIn(filename, view)
        self.assertIn("P1", view)
        self.assertIn("P0", view)  # unsorted

    def test_identical_copy_follows_the_original_and_takes_the_stricter_label(self):
        original = self.folder / "buyers_order.pdf"
        (self.folder / "buyers_order (1).pdf").write_bytes(original.read_bytes())
        self.assigned["buyers_order (1).pdf"] = {"primary": "Unsorted", "also": [], "sensitivity": "none"}
        self.assigned["buyers_order.pdf"]["sensitivity"] = "financial"
        text = self.plan()
        row = next(line for line in text.splitlines() if line.startswith("| buyers_order (1).pdf"))
        self.assertIn("Projects/Car purchase/_duplicates/buyers_order (1).pdf", row)
        self.assertIn("sensitivity=financial", row)

    def test_empty_file_goes_to_unsorted_whatever_the_model_said(self):
        (self.folder / "empty.pdf").write_bytes(b"")
        self.assigned["empty.pdf"] = {"primary": "Tax prep", "also": [], "sensitivity": "financial"}
        self.assertIn("| empty.pdf | Projects/_Unsorted/empty.pdf |", self.plan())

    def test_missing_answer_fails_closed(self):
        del self.assigned["w2_2025.pdf"]
        text = self.plan()
        self.assertIn("| w2_2025.pdf | Projects/_Unsorted/w2_2025.pdf | project=Unsorted sensitivity=unknown |", text)
        first = (self.root / "protect-list.txt").read_text().splitlines()[2]
        self.assertTrue(first.startswith("Unsorted"), first)  # unknown outranks everything

    def test_protect_list_ranks_projects_by_their_most_sensitive_file(self):
        self.assigned["w2_2025.pdf"]["sensitivity"] = "government_id"
        for name in ("Zoom.dmg", "vpn-client.dmg"):
            self.assigned[name]["sensitivity"] = "none"
        self.plan()
        lines = (self.root / "protect-list.txt").read_text().splitlines()[2:]
        self.assertTrue(lines[0].startswith("Tax prep"), lines[0])
        self.assertIn("highest: government_id", lines[0])
        for line in lines[-2:]:  # Software and Unsorted hold nothing sensitive, so they come last
            self.assertIn("highest: none", line)

    def test_top_level_mode_moves_subfolders_whole(self):
        (self.folder / "old_project" / "src").mkdir(parents=True)
        (self.folder / "old_project" / "src" / "a.py").write_text("print(1)")
        text = self.plan("--top-level")
        self.assertIn("Mode: top-level", text)
        self.assertIn("| old_project | Folders/old_project |", text)
        self.assertNotIn("a.py", text)
        self.assertEqual(run(CH1 / "apply_plan.py", "--check", self.root / "organize-plan.md", self.folder).returncode, 0)


class FixtureTests(unittest.TestCase):
    def test_blind_mode_blanks_text_without_creating_duplicates(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            done = run(HERE / "make_project_mess.py", Path(tmp) / "d", "--blind")
            self.assertEqual(done.returncode, 0, done.stderr)
            files = list((Path(tmp) / "d").iterdir())
            blanked = [f for f in files if "no text layer" in f.read_text(errors="ignore")]
            self.assertGreater(len(blanked), 15)
            hashes = [hashlib.sha256(f.read_bytes()).hexdigest() for f in files]
            self.assertEqual(len(hashes), len(set(hashes)), "blanked files must not be byte-identical")


class TagTests(Base):
    @unittest.skipUnless(ON_MAC, "Finder tags are macOS only")
    def test_tags_are_added_kept_alongside_existing_ones_and_removed(self):
        plan = self.root / "organize-plan.md"
        self.plan()
        run(CH1 / "apply_plan.py", plan, self.folder)
        moved = self.folder / "Projects" / "Car purchase" / "buyers_order.pdf"
        tag_files.write_tags(moved, ["Red"])  # a tag the user added themselves
        self.assertIn("Would tag", run(HERE / "tag_files.py", "--check", plan, self.folder).stdout)
        self.assertEqual(tag_files.read_tags(moved), ["Red"])  # --check changed nothing
        self.assertEqual(run(HERE / "tag_files.py", plan, self.folder).returncode, 0)
        self.assertEqual(sorted(tag_files.read_tags(moved)), ["Red", "Tax prep"])
        run(HERE / "tag_files.py", "--remove", plan, self.folder)
        self.assertEqual(tag_files.read_tags(moved), ["Red"])  # ours removed, theirs kept


class AssignTests(unittest.TestCase):
    def test_answers_are_cleaned_even_though_the_schema_constrains_them(self):
        names = ["A", "B", "C"]
        got = assign.clean({"primary": "Z", "also": ["B", "B", "Q", "A"], "sensitivity": "bogus"}, names)
        self.assertEqual(got, {"primary": "Unsorted", "also": ["B", "A"], "sensitivity": "unknown"})
        got = assign.clean({"primary": "A", "also": ["A", "B", "C"], "sensitivity": "none"}, names)
        self.assertEqual(got, {"primary": "A", "also": ["B", "C"], "sensitivity": "none"})

    def test_schema_limits_the_model_to_your_project_names(self):
        schema = assign.build_schema(["A", "B"])
        self.assertEqual(schema["properties"]["primary"]["enum"], ["A", "B", "Unsorted"])
        self.assertEqual(schema["properties"]["also"]["items"]["enum"], ["A", "B"])
        self.assertEqual(schema["properties"]["also"]["maxItems"], 2)

    def test_bad_project_names_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for bad in ("a/b", "x|y", "p;q", "Unsorted", ""):
                path = Path(tmp) / "p.json"
                path.write_text(json.dumps([{"name": bad}]))
                with self.assertRaises(SystemExit):
                    assign.load_projects(path)

    def test_signals_can_be_hidden_from_the_model(self):
        shown = assign.build_user("f.pdf", "site.example", "2026-03-02", "text", True, True)
        hidden = assign.build_user("f.pdf", "site.example", "2026-03-02", "text", False, False)
        self.assertIn("site.example", shown)
        self.assertIn("2026-03-02", shown)
        self.assertNotIn("site.example", hidden)
        self.assertNotIn("2026-03-02", hidden)

    @unittest.skipUnless(ON_MAC, "download sources are recorded by macOS")
    def test_download_domain_is_read_from_the_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            run(HERE / "make_project_mess.py", Path(tmp) / "d")
            self.assertEqual(assign.download_domain(Path(tmp) / "d" / "order-88231.pdf"), "maplestone-reno.example")
            self.assertIsNone(assign.download_domain(Path(tmp) / "d" / "scan_0042.pdf"))


class ScoreTests(Base):
    def test_perfect_answers_score_perfectly_and_beat_sorting_by_type(self):
        result = scoring.score(self.truth, self.assigned)
        self.assertEqual(result["accuracy"], 1.0)
        self.assertEqual(result["also_recall"], 1.0)
        self.assertEqual(result["also_precision"], 1.0)
        self.assertLess(result["type_purity"], 0.5)

    def test_giving_up_scores_only_the_unsorted_files(self):
        nothing = {f: {"primary": "Unsorted", "also": []} for f in self.truth}
        result = scoring.score(self.truth, nothing)
        self.assertAlmostEqual(result["accuracy"], 3 / 59)
        self.assertEqual(result["also_recall"], 0.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
