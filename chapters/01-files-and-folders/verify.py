"""Independently check that an agent only rearranged files.

    python verify.py snapshot <folder>   # run BEFORE the agent
    python verify.py check <folder>      # run AFTER the agent

The snapshot records a SHA-256 hash of every file's content. The check
confirms that every original file still exists exactly once, with
unchanged content, and that nothing new appeared. It doesn't care where
files ended up, only that none were lost, changed, or invented.
"""
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


def hash_file(path: Path) -> str:
    # Read in chunks so a multi-GB file never has to fit in memory.
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_folder(folder: Path) -> Counter:
    hashes = Counter()
    for path in folder.rglob("*"):
        # .DS_Store is Finder bookkeeping that appears the moment you open a folder to look.
        if path.is_file() and path.name != ".DS_Store":
            hashes[hash_file(path)] += 1
    return hashes


def manifest_path(folder: Path) -> Path:
    # Stored beside the folder, not inside it, so it is never part of the mess.
    return folder.resolve().parent / f".{folder.name}.manifest.json"


def snapshot(folder: Path) -> None:
    hashes = hash_folder(folder)
    manifest_path(folder).write_text(json.dumps(hashes))
    print(f"Snapshot saved: {sum(hashes.values())} files in {folder}")


def check(folder: Path) -> int:
    path = manifest_path(folder)
    if not path.exists():
        sys.exit("No snapshot found. Run `snapshot` before the agent runs.")
    before = Counter(json.loads(path.read_text()))
    after = hash_folder(folder)
    lost, extra = before - after, after - before
    if not lost and not extra:
        print(f"PASS: all {sum(before.values())} files accounted for, none changed.")
        return 0
    if lost:
        print(f"FAIL: {sum(lost.values())} file(s) lost or modified.")
    if extra:
        print(f"FAIL: {sum(extra.values())} unexpected new or changed file(s).")
    return 1


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] not in ("snapshot", "check"):
        sys.exit(__doc__)
    target = Path(sys.argv[2])
    if not target.is_dir():
        sys.exit(f"Not a folder: {target}\nCreate it (and copy your files in) first.")
    if sys.argv[1] == "snapshot":
        snapshot(target)
    else:
        sys.exit(check(target))
