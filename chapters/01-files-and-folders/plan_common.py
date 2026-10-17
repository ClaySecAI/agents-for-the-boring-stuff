"""Shared helpers for the plan scripts (make_plan, apply_plan, undo_plan).

A plan is a markdown file with a `| From | To | Why |` table. Two things live beside it:

  * `Mode: top-level` (optional line). In top-level mode each direct child of the
    folder, file OR subfolder, is one item. Subfolders move as a unit and are never
    opened. Without the line the plan is "recursive": every file at any depth is an item.
    The mode is written in the plan itself, so apply, check and undo can never
    disagree about what "covered" means.
  * A row whose From equals its To means "leave this in place". It still counts as
    covered, so a human can keep a folder where it is by editing one cell instead of
    deleting a row (which would break the coverage check).
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# Finder rewrites this file whenever you open a folder, which would make a clean run
# "fail" the moment you look at the result. Only this one name is ignored; other
# dotfiles (.env, .ssh...) are exactly what a sensitivity pass should see.
IGNORED_NAMES = {".DS_Store"}

MODES = ("recursive", "top-level")
ROW = re.compile(r"^\|\s*(?P<src>[^|]+?)\s*\|\s*(?P<dst>[^|]+?)\s*\|")
MODE_LINE = re.compile(r"^Mode:\s*(\S+)\s*$", re.MULTILINE)


def parse_plan(text: str) -> tuple[str, list[tuple[str, str]]]:
    found = MODE_LINE.search(text)
    mode = found.group(1) if found else "recursive"
    if mode not in MODES:
        raise ValueError(f"Unknown plan mode '{mode}' (use one of: {', '.join(MODES)})")
    rows = []
    for line in text.splitlines():
        m = ROW.match(line)
        if not m or m["src"] == "From" or set(m["src"]) <= {"-", " "}:
            continue
        rows.append((m["src"], m["dst"]))
    return mode, rows


def items_in(folder: Path, mode: str) -> set[str]:
    """Everything a plan in this mode must account for."""
    if mode == "top-level":
        return {p.name for p in folder.iterdir() if p.name not in IGNORED_NAMES}
    return {str(p.relative_to(folder)) for p in folder.rglob("*")
            if p.is_file() and p.name not in IGNORED_NAMES}


def state_dir(folder: Path) -> Path:
    """Where the hidden record files live: beside the folder, or in $PLAN_STATE_DIR when it is set.
    Set it for a folder that syncs (iCloud Drive, Dropbox): the records hold file names and would sync too."""
    override = os.environ.get("PLAN_STATE_DIR")
    return Path(override).expanduser().resolve() if override else folder.resolve().parent


def applied_record(folder: Path) -> Path:
    """Where apply_plan.py keeps a copy of the plan it executed, so undo can find it."""
    return state_dir(folder) / f".{folder.name}.applied-plan.md"


def ancestors(rel: str) -> list[str]:
    """'a/b/c.txt' -> ['a/b', 'a'] (deepest first)."""
    parts = rel.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
