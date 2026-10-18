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

The record apply_plan.py keeps is the plan as approved plus one more line, which lists the
folders that apply created. Undo removes those folders and no others.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

# Finder rewrites this file whenever you open a folder, which would make a clean run
# "fail" the moment you look at the result. Only this one name is ignored; other
# dotfiles (.env, .ssh...) are exactly what a sensitivity pass should see.
IGNORED_NAMES = {".DS_Store"}

MODES = ("recursive", "top-level")
# A "|" inside a file name is written as "\|", as markdown tables do. Browsers' "Save as PDF" often
# puts one in the title, and an unescaped one would split the cell and break the plan.
CELL = r"(?:\\\||[^|])+?"
ROW = re.compile(rf"^\|\s*(?P<src>{CELL})\s*\|\s*(?P<dst>{CELL})\s*\|")
MODE_LINE = re.compile(r"^Mode:\s*(\S+)\s*$", re.MULTILINE)
CREATED_LINE = re.compile(r"^Folders created by apply_plan\.py: (.*)$", re.MULTILINE)


def escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def unescape_cell(text: str) -> str:
    return text.replace("\\|", "|")


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
        rows.append((unescape_cell(m["src"]), unescape_cell(m["dst"])))
    return mode, rows


def items_in(folder: Path, mode: str) -> set[str]:
    """Everything a plan in this mode must account for. In recursive mode a link to a file counts as a file;
    apply_plan.py only lets it stay where it is."""
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
    return state_dir(folder) / f".{folder.resolve().name}.applied-plan.md"


def record_text(plan_text: str, created: list[str]) -> str:
    """The plan as approved, plus the folders apply is about to create. The extra line is not a table row,
    so the record still reads as the same plan."""
    return plan_text.rstrip("\n") + f"\n\nFolders created by apply_plan.py: {json.dumps(created)}\n"


def created_folders(text: str) -> list[str] | None:
    """The folders an apply created, read from its record. None for a plain plan, which never says."""
    found = CREATED_LINE.findall(text)
    return json.loads(found[-1]) if found else None


def leaves_folder(folder: Path, rel: str) -> bool:
    """True for a plan path that is absolute, has an empty, `.` or `..` part, or reaches outside the folder
    through a linked folder. The last part is not followed, so a link that points outside may still stay put."""
    if rel.startswith("/") or any(part in ("", ".", "..") for part in rel.split("/")):
        return True
    root = folder.resolve()
    parent = (folder / rel).parent.resolve()
    return parent != root and root not in parent.parents


def ancestors(rel: str) -> list[str]:
    """'a/b/c.txt' -> ['a/b', 'a'] (deepest first)."""
    parts = rel.split("/")[:-1]
    return ["/".join(parts[:i]) for i in range(len(parts), 0, -1)]
