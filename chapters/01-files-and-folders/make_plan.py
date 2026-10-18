"""Turn a local classifier's labels into an organize-plan.md (+ a safe view for Claude).

    python make_plan.py [--top-level] [--out-dir DIR] <classification.json> <folder>

Input: classification.json, {relative_path: {"category": ..., "sensitivity": ...}}.
Any local classifier (1B or 1C) can produce it. This script is deterministic,
no model involved. It:

  * finds exact duplicates by content hash (a clean name beats "name (1)" as the original),
  * gives identical copies the stricter sensitivity label,
  * routes sensitive files (DLP) to _sensitive/<kind>/,
  * routes empty files and "Review" labels to _needs-review/,
  * leaves links where they are (moving one can break it), and never reads through one,
  * never gives two files names that differ only in upper and lower case, which a Mac
    treats as the same name,
  * writes organize-plan.md in the same `From | To | Why` format apply_plan.py reads.
    "Why" holds label codes only, never quoted file content,
  * writes claude-view.txt: the ONLY thing the cloud model gets to see.
    No filenames, no contents: pseudonymous ids, extensions, sizes, labels.

--top-level: for folders with huge subfolder trees (a real Downloads). Only the folder's
direct children are items. Loose files are classified as usual. Each SUBFOLDER becomes one
row, moved as a unit to Folders/<name> and never opened. The plan records `Mode: top-level`.

Both outputs land beside <folder> unless you pass --out-dir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

from plan_common import IGNORED_NAMES

CATEGORIES = {"Documents", "Images", "Spreadsheets", "Installers", "Archives", "Text", "Review"}
SENSITIVITIES = {"personal", "financial", "health", "credentials", "government_id", "legal"}
# A user's own folder with one of these names is left exactly where it is.
RESERVED_FOLDERS = CATEGORIES | {"Folders", "_sensitive", "_duplicates", "_needs-review"}
RESERVED_FOLDED = {name.casefold() for name in RESERVED_FOLDERS}  # `documents` is `Documents` on a Mac


def sha(path: Path) -> str:
    # Chunked, so a multi-GB file never has to fit in memory.
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pick_destination(rel: str, size: int, label: dict, duplicate: bool) -> tuple[str, str]:
    name = Path(rel).name
    category = label.get("category", "Review")
    sensitivity = label.get("sensitivity", "unknown")
    # Fail closed: anything the model said that we do not recognise is treated as sensitive.
    if sensitivity != "none" and sensitivity not in SENSITIVITIES:
        sensitivity = "unknown"
    if category not in CATEGORIES:
        category = "Review"
    if size == 0:
        # An empty file holds nothing sensitive, whatever the model said. Let a human look.
        folder = "_needs-review"
    elif duplicate:
        # A copy of a sensitive file is just as sensitive: keep it inside the sensitive area.
        folder = "_duplicates" if sensitivity == "none" else f"_sensitive/{sensitivity}/_duplicates"
    elif sensitivity != "none":
        folder = f"_sensitive/{sensitivity}"
    elif category == "Review":
        folder = "_needs-review"
    else:
        folder = category
    return f"{folder}/{name}", f"category={category} sensitivity={sensitivity}"


def main(classification: Path, folder: Path, top_level: bool, out_dir: Path | None) -> None:
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    if not classification.is_file():
        sys.exit(f"Classification file not found: {classification}. Run a classifier first.")
    labels = json.loads(classification.read_text())

    # A link is checked first: is_file() and is_dir() follow it, and a moved link can stop working.
    if top_level:
        entries = sorted(p for p in folder.iterdir() if p.name not in IGNORED_NAMES)
        links = [p.name for p in entries if p.is_symlink()]
        files = [p.name for p in entries if p.is_file() and not p.is_symlink()]
        subfolders = [p.name for p in entries if p.is_dir() and not p.is_symlink()]
    else:
        # Only a link to a file is an item in recursive mode (see plan_common.items_in).
        found = sorted(p for p in folder.rglob("*") if p.is_file() and p.name not in IGNORED_NAMES)
        links = [str(p.relative_to(folder)) for p in found if p.is_symlink()]
        files = [str(p.relative_to(folder)) for p in found if not p.is_symlink()]
        subfolders = []

    seen: dict[str, str] = {}
    duplicate_of: dict[str, str] = {}
    # Keep the "clean" name as the original: "report.pdf" beats "report (1).pdf".
    for rel in sorted(files, key=lambda r: (bool(re.search(r" \(\d+\)\.", r)), r)):
        digest = sha(folder / rel)
        if digest in seen and (folder / rel).stat().st_size > 0:
            duplicate_of[rel] = seen[digest]
        else:
            seen.setdefault(digest, rel)

    # Identical bytes must share the stricter sensitivity label. A model can label two copies
    # differently, and neither copy may end up less protected than the other.
    for copy, original in duplicate_of.items():
        a = labels.get(original, {"category": "Review", "sensitivity": "unknown"})
        b = labels.get(copy, {"category": "Review", "sensitivity": "unknown"})
        strict = b["sensitivity"] if a["sensitivity"] == "none" else a["sensitivity"]
        labels[original] = {**a, "sensitivity": strict}
        labels[copy] = {**b, "sensitivity": strict}

    taken: set[str] = set()  # destinations, case folded
    rows = []  # (rel, dest, why, size, kind)  kind: "file" | "folder" | "stay" | "link"
    for rel in files:
        size = (folder / rel).stat().st_size
        label = labels.get(rel, {"category": "Review", "sensitivity": "unknown"})
        dest, why = pick_destination(rel, size, label, rel in duplicate_of)
        base, n = dest, 2
        while dest.casefold() in taken:
            stem, dot, ext = base.rpartition(".")
            dest = f"{stem} ({n}){dot}{ext}" if dot else f"{base} ({n})"
            n += 1
        taken.add(dest.casefold())
        rows.append((rel, dest, why, size, "file"))
    for rel in links:
        rows.append((rel, rel, "link, left in place (moving it could break it)", 0, "link"))
    for name in subfolders:
        if name.casefold() in RESERVED_FOLDED:
            rows.append((name, name, "folder, left in place (its name matches a folder this plan uses)", 0, "stay"))
        else:
            dest = f"Folders/{name}"
            taken.add(dest.casefold())
            rows.append((name, dest, "folder, moved as a unit, not inspected", 0, "folder"))

    where = (out_dir or folder.resolve().parent)
    where.mkdir(parents=True, exist_ok=True)
    mode_line = ["Mode: top-level", ""] if top_level else []
    lines = [f"# Plan for {folder.resolve().name} (made by a local model + make_plan.py)", "", *mode_line,
             "| From | To | Why |", "|---|---|---|"]
    lines += [f"| {rel} | {dest} | {why} |" for rel, dest, why, _size, _kind in rows]
    plan = where / "organize-plan.md"
    plan.write_text("\n".join(lines) + "\n")

    ids = {rel: f"f{i:03d}" for i, (rel, *_rest) in enumerate(rows, 1)}
    view = [f"{len(rows)} items. Each line: id | extension | bytes | labels | destination folder | notes", ""]
    for rel, dest, why, size, kind in rows:
        if kind == "file":
            note = f"duplicate_of={ids[duplicate_of[rel]]}" if rel in duplicate_of else ""
            if "/" in rel:
                note = (note + " in_subfolder=yes").strip()
            view.append(f"{ids[rel]} | {Path(rel).suffix or '(none)'} | {size} | {why} | "
                        f"{dest.rsplit('/', 1)[0]} | {note}")
        elif kind == "link":
            view.append(f"{ids[rel]} | (link) | - | link, not inspected | (left in place) | ")
        else:  # a whole subfolder: no name, no size, no file count
            place = "Folders" if kind == "folder" else "(left in place)"
            view.append(f"{ids[rel]} | (dir) | - | folder, not inspected | {place} | ")
    (where / "claude-view.txt").write_text("\n".join(view) + "\n")
    extra = f", {len(subfolders)} folders moved as units" if subfolders else ""
    print(f"Wrote {plan.name} and claude-view.txt ({len(rows)} items, {len(duplicate_of)} duplicates{extra}).")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("classification", type=Path)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--out-dir", type=Path)
    args = ap.parse_args()
    main(args.classification, args.folder, args.top_level, args.out_dir)
