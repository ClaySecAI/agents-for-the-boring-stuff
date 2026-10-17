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

    # Cluster purity ignores names, so a list the model invented can be scored against the key:
    # for each group the model made, credit the true project that has the most files in it.
    # recovered counts true projects where one group holds at least 70% of that project's files.
    groups = defaultdict(Counter)
    for f in files:
        groups[assigned.get(f, {}).get("primary", UNSORTED)][truth[f]["primary"]] += 1
    cluster_purity = sum(max(c.values()) for c in groups.values()) / len(files)
    true_sizes = Counter(truth[f]["primary"] for f in files)
    real_projects = [p for p in true_sizes if p != UNSORTED]
    recovered = sum(
        any(c[p] >= 0.7 * true_sizes[p] for c in groups.values()) for p in real_projects)
    return {
        "cluster_purity": cluster_purity,
        "recovered": (recovered, len(real_projects)),
        "groups_made": len([g for g in groups if g != UNSORTED]),
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
    found, real = result["recovered"]
    print(f"Ignoring project names: cluster purity {result['cluster_purity']:.0%}, "
          f"{found} of {real} real projects recovered in {result['groups_made']} groups")
    hits, wanted, given = result["also_counts"]
    print(f"Secondary projects: found {hits} of {wanted} that exist, {given} suggested in all")
    print("\nPer project (correct / files):")
    for name, (ok, total) in sorted(result["per_project"].items()):
        print(f"  {name:20} {ok} / {total}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(Path(sys.argv[1]), Path(sys.argv[2]))
