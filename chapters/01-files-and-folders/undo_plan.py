"""Reverse an applied plan: put every item back where it came from.

    python undo_plan.py [--check] <folder>            # uses the record apply_plan.py saved
    python undo_plan.py [--check] <plan.md> <folder>  # or name the plan yourself

For each plan row it moves To back to From. It then removes the folders that apply created,
which the record lists, and ONLY while they are empty, so a folder that was there before is
always kept. A plan you name yourself has no such list, so then no folder is removed.
It never deletes a file of yours. The one exception is a Finder `.DS_Store` file inside a folder it
removes, because Finder writes those whenever you look at a folder.

Safe to re-run. Before moving anything it checks that:

  * every path stays inside <folder>,
  * every item that was moved is still at its new location,
  * nothing has since been put back at an original location (that would be overwritten),
  * rows that were never applied (an interrupted apply) are skipped, not treated as errors.

If anything looks wrong, nothing is moved and the problem is listed. If the apply stopped
before its first move, undo retires the record so the plan can be applied again.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from plan_common import IGNORED_NAMES, applied_record, created_folders, leaves_folder, parse_plan


def classify(rows: list[tuple[str, str]], folder: Path):
    """Sort rows into: applied (To there, From gone), not applied, and problems."""
    applied, not_applied, problems = [], [], []
    for src, dst in rows:
        if src == dst:
            continue  # was left in place
        if leaves_folder(folder, src) or leaves_folder(folder, dst):
            problems.append(f"path leaves the folder: {src} -> {dst}")
            continue
        # lexists, not exists: a link that stopped working when it moved is still there to put back.
        at_src, at_dst = os.path.lexists(folder / src), os.path.lexists(folder / dst)
        if at_dst and not at_src:
            applied.append((src, dst))
        elif at_src and not at_dst:
            not_applied.append((src, dst))
        elif at_src and at_dst:
            problems.append(f"both locations exist, refusing to overwrite: {src}")
        else:
            problems.append(f"item is gone from both locations: {dst}")
    return applied, not_applied, problems


def remove_created(folder: Path, created: list[str]) -> tuple[int, int]:
    """Remove the folders apply created, deepest first, if they are empty. Returns (removed, kept)."""
    removed = kept = 0
    for rel in sorted(created, key=lambda r: r.count("/"), reverse=True):
        path = folder / rel
        if leaves_folder(folder, rel) or path.is_symlink() or not path.is_dir():
            continue
        contents = list(path.iterdir())
        # A folder holding only Finder's .DS_Store bookkeeping counts as empty: every script in this
        # chapter ignores that file, and it appears whenever you look at a folder in Finder.
        if all(item.name in IGNORED_NAMES and item.is_file() for item in contents):
            for item in contents:
                item.unlink()
            os.rmdir(path)
            removed += 1
        else:
            kept += 1
    return removed, kept


def main(plan: Path, folder: Path, check_only: bool, using_record: bool) -> None:
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    if not plan.is_file():
        undone = plan.with_name(plan.name.replace(".applied-plan", ".undone-plan"))
        if using_record and undone.exists():
            sys.exit("Nothing to undo: the last applied plan was already undone.")
        sys.exit(f"No plan to undo: {plan} not found. Was a plan applied to this folder?")
    text = plan.read_text()
    try:
        _mode, rows = parse_plan(text)
        created = created_folders(text)
    except ValueError as err:
        sys.exit(str(err))

    applied, not_applied, problems = classify(rows, folder)
    if problems:
        print("Undo rejected. Nothing was moved.")
        for p in problems[:15]:
            print(f"  - {p}")
        if len(problems) > 15:
            print(f"  ... and {len(problems) - 15} more")
        sys.exit(1)
    if not applied and not using_record:
        sys.exit("Nothing to undo: every item is already back where it came from.")
    skipped = f" ({len(not_applied)} rows were never applied and are skipped)" if not_applied else ""
    if check_only:
        if applied:
            print(f"Undo OK: {len(applied)} items can be put back{skipped}.")
        else:
            print(f"Undo OK: no item had moved. Undo will retire the record ({plan}) so the plan can be applied again.")
        return

    for src, dst in applied:
        (folder / src).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(folder / dst, folder / src)
    if created is None:
        folders = "removed no folders (this plan does not list the folders apply created)"
    else:
        removed, kept = remove_created(folder, created)
        folders = f"removed {removed} empty folder(s) that apply created"
        if kept:
            folders += f", kept {kept} that still hold other files"
    if applied:
        print(f"Put back {len(applied)} items, {folders}.{skipped}")
    if using_record:
        retired = plan.with_name(plan.name.replace(".applied-plan", ".undone-plan"))
        plan.rename(retired)
        if not applied:  # the apply stopped before its first move
            print(f"No item had moved, so nothing was put back; {folders}. "
                  f"The record is retired ({retired}), so the plan can be applied again.")


if __name__ == "__main__":
    args = sys.argv[1:]
    if "-h" in args or "--help" in args:
        print(__doc__)
        sys.exit(0)
    check_only = "--check" in args
    args = [a for a in args if a != "--check"]
    unknown = [a for a in args if a.startswith("-")]
    if unknown:
        sys.exit(f"Unknown option: {unknown[0]}\n{__doc__}")
    if len(args) == 1:
        folder, plan, using_record = Path(args[0]), applied_record(Path(args[0])), True
    elif len(args) == 2:
        plan, folder, using_record = Path(args[0]), Path(args[1]), False
    else:
        sys.exit(__doc__)
    main(plan, folder, check_only, using_record)
