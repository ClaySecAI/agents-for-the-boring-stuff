"""Reverse an applied plan: put every item back where it came from.

    python undo_plan.py [--check] <folder>            # uses the record apply_plan.py saved
    python undo_plan.py [--check] <plan.md> <folder>  # or name the plan yourself

For each plan row it moves To back to From. It then removes the folders the plan
created, but ONLY folders that are empty, that sit above a moved item, and that were not
there before (a folder that holds a From path, like a pre-existing `old_stuff/`, is kept).
It never deletes a file.

Safe to re-run. Before moving anything it checks that:

  * every item that was moved is still at its new location,
  * nothing has since been put back at an original location (that would be overwritten),
  * rows that were never applied (an interrupted apply) are skipped, not treated as errors.

If anything looks wrong, nothing is moved and the problem is listed.
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from plan_common import ancestors, applied_record, parse_plan


def classify(rows: list[tuple[str, str]], folder: Path):
    """Sort rows into: applied (To there, From gone), not applied, and problems."""
    applied, not_applied, problems = [], [], []
    for src, dst in rows:
        if src == dst:
            continue  # was left in place
        at_src, at_dst = (folder / src).exists(), (folder / dst).exists()
        if at_dst and not at_src:
            applied.append((src, dst))
        elif at_src and not at_dst:
            not_applied.append((src, dst))
        elif at_src and at_dst:
            problems.append(f"both locations exist, refusing to overwrite: {src}")
        else:
            problems.append(f"item is gone from both locations: {dst}")
    return applied, not_applied, problems


def main(plan: Path, folder: Path, check_only: bool, using_record: bool) -> None:
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    if not plan.is_file():
        undone = plan.with_name(plan.name.replace(".applied-plan", ".undone-plan"))
        if using_record and undone.exists():
            sys.exit("Nothing to undo: the last applied plan was already undone.")
        sys.exit(f"No plan to undo: {plan} not found. Was a plan applied to this folder?")
    try:
        _mode, rows = parse_plan(plan.read_text())
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
    if not applied:
        sys.exit("Nothing to undo: every item is already back where it came from.")
    skipped = f" ({len(not_applied)} rows were never applied and are skipped)" if not_applied else ""
    if check_only:
        print(f"Undo OK: {len(applied)} items can be put back{skipped}.")
        return

    for src, dst in applied:
        (folder / src).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(folder / dst, folder / src)

    # Tidy up only the folders this plan created: empty ones, above a moved item,
    # and not above any original location. Deepest first.
    keep = {a for src, _ in rows for a in ancestors(src)} | {src for src, dst in rows if src == dst}
    candidates = {a for _, dst in applied for a in ancestors(dst)} - keep
    removed = left = 0
    for rel in sorted(candidates, key=lambda r: r.count("/"), reverse=True):
        path = folder / rel
        if path.is_dir() and not any(path.iterdir()):
            os.rmdir(path)
            removed += 1
        elif path.is_dir():
            left += 1
    if using_record:
        record = applied_record(folder)
        record.rename(record.with_name(record.name.replace(".applied-plan", ".undone-plan")))
    extra = f" {left} folder(s) still hold other files and were kept." if left else ""
    print(f"Put back {len(applied)} items, removed {removed} empty folder(s).{skipped}{extra}")


if __name__ == "__main__":
    args = sys.argv[1:]
    check_only = "--check" in args
    args = [a for a in args if a != "--check"]
    if len(args) == 1:
        folder, plan, using_record = Path(args[0]), applied_record(Path(args[0])), True
    elif len(args) == 2:
        plan, folder, using_record = Path(args[0]), Path(args[1]), False
    else:
        sys.exit(__doc__)
    main(plan, folder, check_only, using_record)
