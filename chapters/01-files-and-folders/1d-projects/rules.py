"""Rules learned from your corrections. Exact signals only: no similarity, no model.

    python3 rules.py learn <folder> <projects.json> <corrections.json> [--assignments FILE] [--out FILE]
    python3 rules.py apply <folder> <assignments.json> <rules.json> [--out FILE] [--top-level]

When you tell the tool which project a file belongs to, it can notice what that file has in common
with others that belong there, and remember it as a rule. A rule is an exact match on one of:

  identifier  an account, loan, claim or case number that appears in the file's text
  path        the file's own relative path (your decision about that exact file)
  domain      the website the file was downloaded from
  name_key    the file's name with digits and punctuation stripped ("account_history (2).pdf"
              becomes "account history"). Names too short to mean anything are ignored

`learn` writes rules.json. A signal becomes a rule only if the files you labelled with it all agree
on one project, and enough of them do (a domain or a name pattern needs two; an identifier or an exact
path needs one). A website you used for two different projects, such as a bank, therefore makes no rule.

`apply` runs the rules over a set of assignments, after the model has run. For each file it collects
the projects that matching rules point to. If they agree, the rule's project replaces the model's
answer. If they disagree, nothing changes and the model's answer stands. Files a rule fixed are marked
"source": "rule".

Rules name your websites, account numbers and projects. Treat rules.json and corrections.json as
private: they are listed in .gitignore and refused by the repository's commit guard.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
sys.path.insert(0, str(HERE))
import assign_projects as assign  # noqa: E402
import classify_local as local  # noqa: E402
import link_files  # noqa: E402

UNSORTED = assign.UNSORTED
PRIORITY = ("identifier", "path", "domain", "name_key")  # exact and personal first, loose patterns last
MIN_SUPPORT = {"identifier": 1, "path": 1, "domain": 2, "name_key": 2}


def name_key(filename: str) -> str:
    """'account_history (2).pdf' -> 'account history'. Empty when too little letter content remains."""
    key = re.sub(r"[^a-z]+", " ", Path(filename).stem.lower()).strip()
    return key if len(key.replace(" ", "")) >= 5 else ""


def signals(path: Path, rel: str) -> dict:
    text = local.read_head(path, 20000) if path.is_file() else ""
    return {
        "identifier": sorted(link_files.extract_identifiers(text)),
        "path": [rel],
        "domain": [d] if (d := assign.download_domain(path)) else [],
        "name_key": [k] if (k := name_key(path.name)) else [],
    }


def learn(labelled: list[tuple[dict, str]], min_support: dict[str, int] | None = None) -> tuple[list[dict], int]:
    """From (signals, project) pairs make rules. Returns (rules, how many signals were dropped for disagreeing)."""
    need = {**MIN_SUPPORT, **(min_support or {})}
    seen: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for sig, project in labelled:
        for kind in PRIORITY:
            for value in sig.get(kind, []):
                seen[(kind, value)][project] += 1
    rules, dropped = [], 0
    for (kind, value), counts in sorted(seen.items()):
        if len(counts) > 1:
            dropped += 1  # the same signal was labelled with two projects: it proves nothing
            continue
        (project, support), = counts.items()
        if project != UNSORTED and support >= need[kind]:
            rules.append({"kind": kind, "value": value, "project": project, "support": support})
    return rules, dropped


def decide(rules: list[dict], sig: dict) -> tuple[str | None, str]:
    """The project the matching rules agree on, or None. Second value says why: match, none or disagree."""
    index = defaultdict(set)
    for rule in rules:
        index[(rule["kind"], rule["value"])].add(rule["project"])
    hits: set[str] = set()
    for kind in PRIORITY:
        for value in sig.get(kind, []):
            hits |= index.get((kind, value), set())
    if not hits:
        return None, "none"
    if len(hits) > 1:
        return None, "disagree"
    return next(iter(hits)), "match"


def apply_rules(assigned: dict, sigs: dict[str, dict], rules: list[dict]) -> tuple[dict, dict]:
    """Return (new assignments, counts). Never touches a file no rule matches."""
    new = {k: {**v, "also": list(v.get("also", []))} for k, v in assigned.items()}
    counts = {"matched": 0, "changed": 0, "disagree": 0, "untouched": 0}
    for rel, sig in sigs.items():
        if rel not in new:
            continue
        project, why = decide(rules, sig)
        if why == "match":
            counts["matched"] += 1
            if new[rel]["primary"] != project:
                counts["changed"] += 1
            new[rel]["primary"] = project
            new[rel]["also"] = [a for a in new[rel]["also"] if a != project]
            new[rel]["source"] = "rule"
        else:
            counts["disagree" if why == "disagree" else "untouched"] += 1
    return new, counts


def list_files(folder: Path, top_level: bool) -> list[Path]:
    candidates = folder.iterdir() if top_level else folder.rglob("*")
    return sorted(p for p in candidates if p.is_file() and p.name != ".DS_Store"
                  and not (top_level and p.name.startswith(".")))


def cmd_learn(args) -> None:
    projects = {p["name"] for p in assign.load_projects(args.projects)}
    corrections = json.loads(args.corrections.read_text())
    labelled = []
    for item in corrections:
        path = args.folder / item["path"]
        if item["project"] in projects | {UNSORTED} and path.is_file():
            labelled.append((signals(path, item["path"]), item["project"]))
    rules, dropped = learn(labelled)
    out = args.out or args.corrections.with_name("rules.json")
    out.write_text(json.dumps(rules, indent=2))
    by_kind = {k: sum(1 for r in rules if r["kind"] == k) for k in PRIORITY}
    print(f"{len(labelled)} corrections -> {len(rules)} rules "
          f"({', '.join(f'{n} {k}' for k, n in by_kind.items())}); {dropped} signals dropped because they disagreed.")
    if args.assignments:
        assigned = json.loads(args.assignments.read_text())
        files = list_files(args.folder, args.top_level)
        sigs = {str(p.relative_to(args.folder)): signals(p, str(p.relative_to(args.folder))) for p in files}
        _new, counts = apply_rules(assigned, sigs, rules)
        print(f"preview on the {len(files)} files here: {counts['matched']} would be decided by a rule, "
              f"{counts['changed']} of those would change from the model's answer, "
              f"{counts['disagree']} left alone because rules disagree.")
    print(f"wrote {out.name}")


def cmd_apply(args) -> None:
    rules = json.loads(args.rules.read_text())
    assigned = json.loads(args.assignments.read_text())
    files = list_files(args.folder, args.top_level)
    sigs = {str(p.relative_to(args.folder)): signals(p, str(p.relative_to(args.folder))) for p in files}
    new, counts = apply_rules(assigned, sigs, rules)
    out = args.out or args.assignments.with_name("assignments-ruled.json")
    out.write_text(json.dumps(new, indent=2))
    print(f"{counts['matched']} files decided by a rule ({counts['changed']} changed from the model's answer), "
          f"{counts['disagree']} left to the model because rules disagreed, {counts['untouched']} matched no rule.")
    print(f"wrote {out.name}")


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("learn")
    p.add_argument("folder", type=Path)
    p.add_argument("projects", type=Path)
    p.add_argument("corrections", type=Path)
    p.add_argument("--assignments", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--top-level", action="store_true")
    p.set_defaults(run=cmd_learn)
    p = sub.add_parser("apply")
    p.add_argument("folder", type=Path)
    p.add_argument("assignments", type=Path)
    p.add_argument("rules", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--top-level", action="store_true")
    p.set_defaults(run=cmd_apply)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
