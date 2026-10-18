"""Check, then apply, an approved organize-plan.md.

    python apply_plan.py --check <plan.md> <folder>   # validate only, move nothing
    python apply_plan.py <plan.md> <folder>           # validate, then move

Reads the plan's `| From | To | Why |` table (paths relative to <folder>). The plan's
`Mode:` line decides what counts as an item: every file at any depth (default), or only
the folder's direct children with subfolders moved as single units (`Mode: top-level`).
See plan_common.py.

Before moving anything it checks that:

  * every path stays inside <folder> (no absolute paths, no `..`),
  * every `From` exists, and no link is moved (a moved link can stop working),
  * no `To` already exists, and no two rows share a `To`. Names that differ only in
    upper and lower case count as the same, because on a Mac they are,
  * no `To` is a folder that another row puts an item in or takes one from,
  * the plan covers EVERY item in the folder (a plan that quietly skips things is
    rejected, and the skipped ones are listed),
  * no earlier applied plan is still waiting to be undone.

If any check fails, nothing is moved. Before the first move, a record is saved beside the
folder (see plan_common.applied_record): the plan, plus the folders this run creates, so
undo_plan.py can reverse it. Each move checks once more that nothing sits at its `To`; if a
move cannot be made, the run stops there and says how to undo the moves already made.
Because this script does exactly what the table says, what you approved is what happens.
"""
from __future__ import annotations

import os
import shutil
import sys
from collections import Counter
from pathlib import Path

from plan_common import ancestors, applied_record, items_in, leaves_folder, parse_plan, record_text


def preflight(rows: list[tuple[str, str]], folder: Path, mode: str) -> list[str]:
    # A Mac treats `Invoice.pdf` and `invoice.pdf` as one name, so every comparison of two paths folds case.
    problems = []
    sources = [src for src, _ in rows]
    listed = Counter(src.casefold() for src in sources)
    for src in sorted({s for s in sources if listed[s.casefold()] > 1}):
        problems.append(f"item listed more than once: {src}")
    outside = {path for row in rows for path in row if leaves_folder(folder, path)}
    for path in sorted(outside):
        problems.append(f"path leaves the folder (write it relative to the folder, without ..): {path}")
    for src, dst in rows:
        if src in outside:
            continue
        if mode == "top-level" and "/" in src:
            problems.append(f"top-level plan lists a nested path: {src}")
        elif not os.path.lexists(folder / src):
            problems.append(f"source missing: {src}")
        elif src != dst and (folder / src).is_symlink():
            problems.append(f"a link cannot be moved, it could stop working (make its To the same as its From): {src}")

    # src == dst means "leave in place"
    moving = [(src, dst) for src, dst in rows if src != dst and not {src, dst} & outside]
    destinations = sorted({dst for _, dst in moving})
    planned = Counter(dst.casefold() for _, dst in moving)
    for dst in destinations:
        if os.path.lexists(folder / dst):
            problems.append(f"would overwrite existing item: {dst}")
    for folded in sorted(k for k, n in planned.items() if n > 1):
        names = [d for d in destinations if d.casefold() == folded]
        same = names[0] if len(names) == 1 else f"{', '.join(names)} (on a Mac these names are the same)"
        problems.append(f"two items planned for the same destination: {same}")

    moved = {src.casefold() for src, _ in moving}
    folders_used = {a.casefold() for path in sources + destinations for a in ancestors(path)}
    nesting = set()
    for dst in destinations:
        if dst.casefold() in folders_used:
            nesting.add(f"destination is also a folder this plan puts items in or takes them from: {dst}")
        for folder_rel in ancestors(dst):
            if folder_rel.casefold() in moved:
                nesting.add(f"destination folder '{folder_rel}' is itself an item this plan moves")
            elif os.path.lexists(folder / folder_rel) and not (folder / folder_rel).is_dir():
                nesting.add(f"destination folder '{folder_rel}' is a file")
    problems += sorted(nesting)

    for skipped in sorted(items_in(folder, mode) - set(sources)):
        problems.append(f"plan skips this item: {skipped}")
    return problems


def main(plan: Path, folder: Path, check_only: bool) -> None:
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    if not plan.is_file():
        sys.exit(f"Plan not found: {plan}")
    text = plan.read_text()
    try:
        mode, rows = parse_plan(text)
    except ValueError as err:
        sys.exit(str(err))
    if not rows:
        sys.exit("No rows found in the plan table.")

    problems = preflight(rows, folder, mode)
    record = applied_record(folder)
    if record.exists():
        # First, so it is the reason you see (the folder is already organized, so a flood of
        # "source missing" errors would follow and bury it).
        problems.insert(0, f"an earlier applied plan is still on record ({record}); "
                           f"undo it first: python3 undo_plan.py {folder}")
    if problems:
        print("Plan rejected. Nothing was moved.")
        for p in problems[:15]:
            print(f"  - {p}")
        if len(problems) > 15:
            print(f"  ... and {len(problems) - 15} more")
        sys.exit(1)

    moving = [(src, dst) for src, dst in rows if src != dst]
    stay = len(rows) - len(moving)
    note = f", {stay} left in place" if stay else ""
    if check_only:
        print(f"Plan OK ({mode} mode): {len(moving)} moves{note}, everything in the folder is covered.")
        return
    # Written before the first move, so even an interrupted run can be undone. It names the folders this run
    # is about to create: undo removes those, and never a folder that was already there.
    created = sorted({a for _, dst in moving for a in ancestors(dst) if not os.path.lexists(folder / a)})
    record.write_text(record_text(text, created))
    done = 0
    try:
        for src, dst in moving:
            if os.path.lexists(folder / dst):  # the check passed, but something may have arrived since
                raise FileExistsError(f"{dst} already exists, and it was left alone")
            (folder / dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(folder / src, folder / dst)
            done += 1
    except OSError as err:
        print(f"Apply interrupted after {done} of {len(moving)} moves: {err}")
        print(f"Put back what moved with: python3 undo_plan.py {folder}")
        sys.exit(1)
    print(f"Moved {done} items{note}. Record: {record}")
    print(f"Undo with: python3 undo_plan.py {folder}")


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
    if len(args) != 2:
        sys.exit(__doc__)
    main(Path(args[0]), Path(args[1]), check_only)
