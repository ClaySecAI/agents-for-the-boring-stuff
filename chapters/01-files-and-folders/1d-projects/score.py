"""Score an assignment run against the answer key, and against sorting by file type.

    python3 score.py <truth.json> <assignments.json>

truth.json comes from make_project_mess.py. The score prints:

  * primary accuracy: how often the file landed in its true project
  * recall per project
  * "also" recall and precision: the secondary projects found and the ones that were wrong
  * the baseline: if you sorted by file extension instead, the best-case share of files that
    would sit in the right project. For each extension, take the project that has the most files
    with that extension and count only those. This is the cluster purity of sorting by type.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

UNSORTED = "Unsorted"


def score(truth: dict, assigned: dict) -> dict:
    files = sorted(truth)
    correct = sum(assigned.get(f, {}).get("primary", UNSORTED) == truth[f]["primary"] for f in files)
    per_project = defaultdict(lambda: [0, 0])  # name -> [correct, total]
    for f in files:
        per_project[truth[f]["primary"]][1] += 1
        if assigned.get(f, {}).get("primary", UNSORTED) == truth[f]["primary"]:
            per_project[truth[f]["primary"]][0] += 1

    true_also = {(f, a) for f in files for a in truth[f]["also"]}
    got_also = {(f, a) for f in files for a in assigned.get(f, {}).get("also", [])}
    hits = len(true_also & got_also)

    by_type = defaultdict(Counter)
    for f in files:
        by_type[Path(f).suffix.lower() or "(none)"][truth[f]["primary"]] += 1
    purity = sum(max(c.values()) for c in by_type.values()) / len(files)
    return {
        "files": len(files),
        "accuracy": correct / len(files),
        "per_project": {k: tuple(v) for k, v in per_project.items()},
        "also_recall": hits / len(true_also) if true_also else None,
        "also_precision": hits / len(got_also) if got_also else None,
        "also_counts": (hits, len(true_also), len(got_also)),
        "type_purity": purity,
    }


def main(truth_path: Path, assigned_path: Path) -> None:
    result = score(json.loads(truth_path.read_text()), json.loads(assigned_path.read_text()))
    n = result["files"]
    print(f"Files scored: {n}")
    print(f"Primary project correct: {round(result['accuracy'] * n)} of {n} ({result['accuracy']:.0%})")
    print(f"Sorting by file extension would reach at best: {result['type_purity']:.0%}")
    hits, wanted, given = result["also_counts"]
    print(f"Secondary projects: found {hits} of {wanted} that exist, {given} suggested in all")
    print("\nPer project (correct / files):")
    for name, (ok, total) in sorted(result["per_project"].items()):
        print(f"  {name:20} {ok} / {total}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
