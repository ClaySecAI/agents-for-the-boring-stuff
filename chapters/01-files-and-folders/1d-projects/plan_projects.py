"""Turn project assignments into a project-first plan.

    python3 plan_projects.py [--top-level [--keep-folders]] [--flat] [--out-dir DIR] <assignments.json> <projects.json> <folder>

Each file moves to Projects/<its project>/, or, with --flat, to <its project>/ directly inside the
folder. Nested is the default because everything the tool made then sits in one place that can be
seen, and removed by undo, at a glance, and cannot merge with folders you already have. Flat is
tidier, and it refuses to run when a project name matches an existing item. Sensitivity no longer
decides the folder. A mortgage
refinance needs its pay stubs, tax forms and contract in one place, and splitting them by kind of
sensitive data would undo that. Instead each project inherits the highest sensitivity among its
files, and protect-list.txt ranks the projects so you know which to protect first.

A file that also serves another project stays in one folder (its primary project). The plan's
fourth column, Also, names the other projects, and tag_files.py turns them into Finder tags.

Writes three files beside <folder> (or into --out-dir):

  organize-plan.md   | From | To | Why | Also |, readable by apply_plan.py and undo_plan.py
  claude-view.txt    what Claude may see: ids, extensions, sizes, dates and project ids (P1, P2...).
                     No file names, no project names, no contents.
  protect-list.txt   project names ranked by sensitivity. Local only; it names your projects.

Identical copies stay together in Projects/<project>/_duplicates/ and share the stricter
sensitivity label. Empty files go to Projects/_Empty (review for deletion)/ and anything unassigned
goes to Projects/_Unsorted/.

With --top-level, subfolders move as single units to Folders/<name>, as in Chapter 1. Add
--keep-folders to leave every subfolder exactly where it is instead; only the loose files move.
That is the safest way to start on a real folder. In top-level mode, hidden items (names that begin
with a dot) are always left in place: they are not yours to sort, and moving some of them confuses
the applications that own them. Left-in-place items still appear in the plan, with the same From
and To, so the coverage check stays satisfied.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

CH1 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CH1))
from make_plan import sha  # noqa: E402
from plan_common import IGNORED_NAMES  # noqa: E402

UNSORTED = "Unsorted"
# Most protective first. An unlabelled file ("unknown") counts as the most sensitive.
SEVERITY = ["unknown", "credentials", "government_id", "health", "financial", "legal", "personal", "none"]
RESERVED = {"Projects", "Folders"}
EMPTY = "(empty)"
EMPTY_NAME = "_Empty (review for deletion)"
UNSORTED_NAME = "_Unsorted"


def is_blank(path: Path) -> bool:
    """Zero bytes, or a tiny file holding only whitespace. Nothing in it can say which project it
    belongs to, and it is a candidate for deletion, which is a decision for you. Nothing here
    deletes anything."""
    size = path.stat().st_size
    return size == 0 or (size <= 256 and not path.read_bytes().strip())


def stricter(a: str, b: str) -> str:
    rank = lambda s: SEVERITY.index(s) if s in SEVERITY else 0  # noqa: E731
    return a if rank(a) <= rank(b) else b


def folder_name(project: str) -> str:
    return re.sub(r"[\\/|:;]+", "-", project).strip(". ") or "Project"


def main(assignments: Path, projects_file: Path, folder: Path, top_level: bool, out_dir: Path | None,
         keep_folders: bool = False, flat: bool = False) -> None:
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    for needed in (assignments, projects_file):
        if not needed.is_file():
            sys.exit(f"File not found: {needed}")
    root = "" if flat else "Projects/"  # where the project folders go: inside Projects/, or directly in the folder
    assigned = json.loads(assignments.read_text())
    names = [p["name"] for p in json.loads(projects_file.read_text())]
    if flat:
        # Project folders will sit next to your own items. A name that matches one of them would pour
        # the files into your folder, which is the opposite of leaving it alone. Refuse instead.
        mine = {p.name.lower() for p in folder.iterdir()}
        clashes = sorted({folder_name(n) for n in names + [UNSORTED_NAME, EMPTY_NAME]
                          if folder_name(n).lower() in mine})
        if clashes:
            sys.exit("Flat layout would merge files into existing items named: " + ", ".join(clashes)
                     + ". Rename those projects in the list (or drop --flat).")
    ids = {UNSORTED: "P0", EMPTY: "PE", **{name: f"P{i}" for i, name in enumerate(names, 1)}}

    if top_level:
        entries = sorted(p for p in folder.iterdir() if p.name not in IGNORED_NAMES)
        hidden = [p.name for p in entries if p.name.startswith(".")]
        files = [p.name for p in entries if p.is_file() and not p.name.startswith(".")]
        subfolders = [p.name for p in entries if p.is_dir() and not p.name.startswith(".")]
    else:
        hidden = []
        files = sorted(str(p.relative_to(folder)) for p in folder.rglob("*")
                       if p.is_file() and p.name not in IGNORED_NAMES)
        subfolders = []

    labels = {rel: dict(assigned.get(rel, {"primary": UNSORTED, "also": [], "sensitivity": "unknown"}))
              for rel in files}
    blank = {rel for rel in files if is_blank(folder / rel)}
    seen: dict[str, str] = {}
    duplicate_of: dict[str, str] = {}
    for rel in sorted(files, key=lambda r: (bool(re.search(r" \(\d+\)\.", r)), r)):  # clean names first
        digest = sha(folder / rel)
        if digest in seen and rel not in blank:
            duplicate_of[rel] = seen[digest]
        else:
            seen.setdefault(digest, rel)
    for copy, original in duplicate_of.items():  # identical bytes: same project, stricter label
        both = stricter(labels[copy]["sensitivity"], labels[original]["sensitivity"])
        labels[copy] = {**labels[original], "sensitivity": both}
        labels[original]["sensitivity"] = both

    taken: set[str] = set()
    rows = []  # (rel, dest, why, also, size, kind)
    for rel in files:
        label, size = labels[rel], (folder / rel).stat().st_size
        if rel in blank:
            primary, label = EMPTY, {**label, "sensitivity": "none", "also": []}
        else:
            primary = label["primary"]
        home = (f"{root}{EMPTY_NAME}" if primary == EMPTY else f"{root}{UNSORTED_NAME}" if primary == UNSORTED
                else f"{root}{folder_name(primary)}")
        if rel in duplicate_of:
            home += "/_duplicates"
        base = dest = f"{home}/{Path(rel).name}"
        n = 2
        while dest in taken:
            stem, dot, ext = base.rpartition(".")
            dest = f"{stem} ({n}){dot}{ext}" if dot else f"{base} ({n})"
            n += 1
        taken.add(dest)
        also = [] if primary in (UNSORTED, EMPTY) else label["also"]
        rows.append((rel, dest, f"project={primary} sensitivity={label['sensitivity']}",
                     ";".join(also), size, "file", primary, label["sensitivity"]))
    for name in hidden:
        rows.append((name, name, "hidden item, left in place", "", 0, "stay", "", "none"))
    for name in subfolders:
        if name in RESERVED or keep_folders:
            rows.append((name, name, "folder, left in place", "", 0, "stay", "", "none"))
        else:
            rows.append((name, f"Folders/{name}", "folder, moved as a unit, not inspected", "", 0, "folder", "", "none"))

    where = out_dir or folder.resolve().parent
    where.mkdir(parents=True, exist_ok=True)
    mode_line = ["Mode: top-level", ""] if top_level else []
    plan = ["# Plan for " + folder.name + " (by project, made by a local model + plan_projects.py)", "",
            *mode_line, "| From | To | Why | Also |", "|---|---|---|---|"]
    plan += [f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |" for r in rows]
    (where / "organize-plan.md").write_text("\n".join(plan) + "\n")

    item_id = {r[0]: f"f{i:03d}" for i, r in enumerate(rows, 1)}
    view = [f"{len(rows)} items in {len(names)} projects (P0 is unsorted, PE is empty files held for review). "
            "Each line: id | extension | bytes | modified | project | sensitivity | also | destination folder", ""]
    for rel, dest, _why, also, size, kind, primary, sensitivity in rows:
        if kind != "file":
            # No name, no size, no count of what is inside. "(dir)" moved whole; "(item)" left alone.
            label, place = ("(dir)", "Folders") if kind == "folder" else ("(item)", "(left in place)")
            view.append(f"{item_id[rel]} | {label} | - | - | - | - | - | {place}")
            continue
        modified = datetime.datetime.fromtimestamp((folder / rel).stat().st_mtime).date().isoformat()
        also_ids = ",".join(ids[a] for a in also.split(";") if a in ids) or "-"
        shown = (f"{root}_Unsorted" if primary == UNSORTED else f"{root}_Empty" if primary == EMPTY
                 else f"{root}{ids[primary]}")
        if rel in duplicate_of:
            shown += "/_duplicates"
        dup = f" duplicate_of={item_id[duplicate_of[rel]]}" if rel in duplicate_of else ""
        view.append(f"{item_id[rel]} | {Path(rel).suffix or '(none)'} | {size} | {modified} | {ids[primary]} | "
                    f"{sensitivity} | {also_ids} | {shown}{dup}")
    (where / "claude-view.txt").write_text("\n".join(view) + "\n")

    summary = {}
    for _rel, _dest, _why, _also, _size, kind, primary, sensitivity in rows:
        if kind == "file":
            entry = summary.setdefault(primary or UNSORTED, {"files": 0, "top": "none", "counts": {}})
            entry["files"] += 1
            entry["top"] = stricter(entry["top"], sensitivity)
            entry["counts"][sensitivity] = entry["counts"].get(sensitivity, 0) + 1
    ranked = sorted(summary.items(), key=lambda kv: (SEVERITY.index(kv[1]["top"]) if kv[1]["top"] in SEVERITY else 0, kv[0]))
    lines = ["Projects ranked by the most sensitive thing they hold (protect the top ones first)", ""]
    for name, entry in ranked:
        detail = ", ".join(f"{k} {v}" for k, v in sorted(entry["counts"].items()))
        lines.append(f"{name} | {entry['files']} files | highest: {entry['top']} | {detail}")
    (where / "protect-list.txt").write_text("\n".join(lines) + "\n")

    tagged = sum(1 for r in rows if r[3])
    moved_whole = sum(1 for r in rows if r[5] == "folder")
    left = sum(1 for r in rows if r[5] == "stay")
    extra = (f", {moved_whole} folders moved as units" if moved_whole else "") + \
            (f", {left} items left in place" if left else "")
    print(f"Wrote organize-plan.md, claude-view.txt and protect-list.txt "
          f"({len(rows)} items in {len(summary)} groups, {tagged} with tags, {len(duplicate_of)} duplicates{extra}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("assignments", type=Path)
    ap.add_argument("projects", type=Path)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--keep-folders", action="store_true",
                    help="with --top-level: leave every subfolder where it is; only loose files move")
    ap.add_argument("--flat", action="store_true",
                    help="put the project folders directly in the folder instead of inside Projects/; "
                         "refuses if a project name matches an existing item")
    ap.add_argument("--out-dir", type=Path)
    a = ap.parse_args()
    if a.keep_folders and not a.top_level:
        ap.error("--keep-folders only applies with --top-level (recursive mode has no folder items)")
    main(a.assignments, a.projects, a.folder, a.top_level, a.out_dir, a.keep_folders, a.flat)
