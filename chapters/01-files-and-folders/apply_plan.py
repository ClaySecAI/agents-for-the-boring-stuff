"""Check, then apply, an approved organize-plan.md.

    python apply_plan.py --check <plan.md> <folder>   # validate only, move nothing
    python apply_plan.py <plan.md> <folder>           # validate, then move

Reads the plan's `| From | To | Why |` table (paths relative to <folder>). The plan's
`Mode:` line decides what counts as an item: every file at any depth (default), or only
the folder's direct children with subfolders moved as single units (`Mode: top-level`).
See plan_common.py.

Before moving anything it checks that:

  * every `From` exists,
  * no `To` already exists, and no two rows share a `To`,
  * the plan covers EVERY item in the folder (a plan that quietly skips things is
    rejected, and the skipped ones are listed),
  * no earlier applied plan is still waiting to be undone.

If any check fails, nothing is moved. After a successful move, a copy of the plan is
saved beside the folder (see plan_common.applied_record) so undo_plan.py can reverse it.
Because this script does exactly what the table says, what you approved is what happens.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from plan_common import applied_record, items_in, parse_plan


def preflight(rows: list[tuple[str, str]], folder: Path, mode: str) -> list[str]:
    problems = []
    sources = [src for src, _ in rows]
    for src in sorted({s for s in sources if sources.count(s) > 1}):
        problems.append(f"item listed more than once: {src}")
    for src in sources:
        if mode == "top-level" and "/" in src:
            problems.append(f"top-level plan lists a nested path: {src}")
        elif not (folder / src).exists():
            problems.append(f"source missing: {src}")

    moving = [(src, dst) for src, dst in rows if src != dst]  # src == dst means "leave in place"
    destinations = [dst for _, dst in moving]
    for dst in sorted(set(destinations)):
        if (folder / dst).exists():
            problems.append(f"would overwrite existing item: {dst}")
        if destinations.count(dst) > 1:
            problems.append(f"two items planned for the same destination: {dst}")
    if mode == "top-level":
        moved = {src for src, _ in moving}
        for dst in destinations:
            top = dst.split("/")[0]
            if "/" in dst and top in moved:
                problems.append(f"destination folder '{top}' is itself an item this plan moves")

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
    if record.exists() and not check_only:
        # First, so it is the reason you see (the folder is already organized, so a flood of
        # "source missing" errors would follow and bury it).
        problems.insert(0, f"an earlier applied plan is still on record ({record.name}); "
                           "undo it first, or delete that file if you no longer need it")
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
    record.write_text(text)  # written first, so even an interrupted run can be undone
    for src, dst in moving:
        (folder / dst).parent.mkdir(parents=True, exist_ok=True)
        shutil.move(folder / src, folder / dst)
    print(f"Moved {len(moving)} items{note}. Undo with: python undo_plan.py {folder}")


if __name__ == "__main__":
    args = sys.argv[1:]
    check_only = "--check" in args
    args = [a for a in args if a != "--check"]
    if len(args) != 2:
        sys.exit(__doc__)
    main(Path(args[0]), Path(args[1]), check_only)
