"""Tell the tool where files belong, one at a time. Your answers are saved as corrections.

    python3 teach.py <folder> <projects.json> <assignments.json> [--all] [--top-level] [--out FILE]

By default it walks through the files the model left in Unsorted. With --all it walks through
every file, so you can also fix the ones the model got wrong. For each file it shows the name, the
website it came from, the date and the start of its contents, then asks:

  1..N    the project it belongs to, numbered as in the list shown
  u       keep it unsorted on purpose
  Enter   skip it for now
  q       stop and save

Run this yourself in a terminal. It prints file names and snippets of your files to your screen, which
is the point. Answers go to corrections.json beside the assignments, and `rules.py learn` turns them
into rules that fix future runs.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import Callable

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
sys.path.insert(0, str(HERE))
import assign_projects as assign  # noqa: E402
import classify_local as local  # noqa: E402

UNSORTED = assign.UNSORTED


def teach(items: list[dict], names: list[str], ask: Callable[[dict], str]) -> tuple[list[dict], bool]:
    """Go through `items`, ask about each. Returns (corrections made, whether you stopped early)."""
    done = []
    for item in items:
        answer = ask(item).strip().lower()
        if answer == "q":
            return done, True
        if answer == "":
            continue
        if answer == "u":
            done.append({"path": item["path"], "project": UNSORTED})
        elif answer.isdigit() and 1 <= int(answer) <= len(names):
            done.append({"path": item["path"], "project": names[int(answer) - 1]})
        # anything else is ignored; the file stays undecided
    return done, False


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("projects", type=Path)
    ap.add_argument("assignments", type=Path)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    names = [p["name"] for p in assign.load_projects(args.projects)]
    assigned = json.loads(args.assignments.read_text())
    out = args.out or args.assignments.with_name("corrections.json")
    existing = json.loads(out.read_text()) if out.exists() else []
    already = {c["path"] for c in existing}

    todo = [rel for rel, v in sorted(assigned.items())
            if (args.all or v["primary"] == UNSORTED) and rel not in already]
    if not todo:
        print("Nothing to go through.")
        return
    print("Projects:")
    for i, name in enumerate(names, 1):
        print(f"  {i}. {name}")
    print(f"\n{len(todo)} files to go through. Type a number, u (stay unsorted), Enter (skip) or q (stop).\n")

    items = []
    for rel in todo:
        path = args.folder / rel
        items.append({"path": rel, "model": assigned[rel]["primary"],
                      "domain": assign.download_domain(path) or "unknown",
                      "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat(),
                      "text": " ".join(local.read_head(path, 300).split())})

    counter = {"n": 0}

    def ask(item: dict) -> str:
        counter["n"] += 1
        print(f"[{counter['n']}/{len(items)}] {item['path']}")
        print(f"    from {item['domain']}, modified {item['modified']}, the model said: {item['model']}")
        print(f"    {item['text'][:300]}")
        return input("    project number > ")

    done, stopped = teach(items, names, ask)
    by_path = {c["path"]: c for c in existing}
    by_path.update({c["path"]: c for c in done})
    out.write_text(json.dumps(sorted(by_path.values(), key=lambda c: c["path"]), indent=2))
    print(f"\nSaved {len(done)} new corrections ({len(by_path)} in all) to {out.name}"
          + (" (stopped early)." if stopped else "."))


if __name__ == "__main__":
    main()
