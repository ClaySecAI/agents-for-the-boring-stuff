"""Add Finder tags for the "also" projects of files in an applied plan (macOS).

    python3 tag_files.py [--check | --remove] <plan.md> <folder>

A file lives in one folder, its primary project. When it also serves other projects, the plan's
Also column names them, and this script gives the file one Finder tag per extra project. In
Finder, click a tag in the sidebar to see every file tagged with it, wherever it is stored.

  (no flag)   add the tags, keeping any tags a file already has
  --check     report what would be tagged; change nothing
  --remove    take those tags off again (tags you added yourself stay)

Run it after apply_plan.py. The tag travels with the file when it moves, so undo_plan.py does not
need to know about tags; run this script with --remove to clear them.

Finder tags are stored as an extended attribute, and tag names are visible in Finder and may be
synced by iCloud if the folder is in iCloud Drive. A tag named after a sensitive project says that
project exists, so think before tagging files in a synced folder.
"""
from __future__ import annotations

import plistlib
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from plan_common import CELL, unescape_cell  # noqa: E402

TAG_ATTR = "com.apple.metadata:_kMDItemUserTags"
ROW = re.compile(rf"^\|\s*({CELL})\s*\|\s*({CELL})\s*\|\s*([^|]*?)\s*\|\s*([^|]*?)\s*\|\s*$")


def read_tags(path: Path) -> list[str]:
    done = subprocess.run(["xattr", "-px", TAG_ATTR, str(path)], capture_output=True, text=True)
    if done.returncode != 0:
        return []
    try:
        return [str(t) for t in plistlib.loads(bytes.fromhex("".join(done.stdout.split())))]
    except Exception:
        return []


def write_tags(path: Path, tags: list[str]) -> None:
    if tags:
        blob = plistlib.dumps(tags, fmt=plistlib.FMT_BINARY).hex()
        subprocess.run(["xattr", "-wx", TAG_ATTR, blob, str(path)], check=True, capture_output=True)
    else:
        subprocess.run(["xattr", "-d", TAG_ATTR, str(path)], capture_output=True)


def tag_name(tag: str) -> str:
    return tag.split("\n")[0]  # Finder stores "Name\n<color number>"


def rows_with_also(plan: Path) -> list[tuple[str, str, list[str]]]:
    rows = []
    for line in plan.read_text().splitlines():
        m = ROW.match(line)
        if not m or m.group(1) == "From" or set(m.group(1)) <= {"-", " "}:
            continue
        also = [a.strip() for a in m.group(4).split(";") if a.strip()]
        if also:
            rows.append((unescape_cell(m.group(1)), unescape_cell(m.group(2)), also))
    return rows


def main(plan: Path, folder: Path, mode: str) -> None:
    if sys.platform != "darwin":
        sys.exit("Finder tags are a macOS feature. On other systems, read the Also column in the plan instead.")
    if not folder.is_dir() or not plan.is_file():
        sys.exit("Need an existing plan file and folder.")
    changed = tags_changed = missing = 0
    for source, dest, also in rows_with_also(plan):
        path = folder / dest if (folder / dest).exists() else folder / source
        if not path.exists():
            missing += 1
            continue
        current = read_tags(path)
        have = {tag_name(t) for t in current}
        if mode == "remove":
            kept = [t for t in current if tag_name(t) not in also]
            delta = len(current) - len(kept)
            if delta and mode != "check":
                write_tags(path, kept)
        else:
            additions = [t for t in also if t not in have]
            delta = len(additions)
            if delta and mode == "apply":
                write_tags(path, current + additions)
        if delta:
            changed += 1
            tags_changed += delta
    verb = {"apply": "Tagged", "check": "Would tag", "remove": "Removed tags from"}[mode]
    note = f" {missing} listed file(s) were not found." if missing else ""
    print(f"{verb} {changed} file(s) with {tags_changed} tag(s).{note}")


if __name__ == "__main__":
    args = sys.argv[1:]
    mode = "check" if "--check" in args else "remove" if "--remove" in args else "apply"
    args = [a for a in args if a not in ("--check", "--remove")]
    if len(args) != 2:
        sys.exit(__doc__)
    main(Path(args[0]), Path(args[1]), mode)
