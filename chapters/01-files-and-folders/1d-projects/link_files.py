"""Give files that share an account, loan, claim or case number the same project.

    python3 link_files.py <folder> <projects.json> <assignments.json> [options]

assign_projects.py judges each file alone, so three monthly statements that say only "Account
number 8841-2290-17" and a table of payments can end up in three different places. A shared
account number is strong evidence that files belong together. This step:

  1. finds identifiers that follow a keyword such as "account number", "loan no.", "claim #"
     or "case ID" in each file's text
  2. links files that share an identifier (an identifier found in more than --max-share files
     is ignored: a bank account number that appears everywhere links nothing)
  3. for each linked group whose members do not already agree, asks the local model ONCE, showing
     it a piece of every member, which single project the group belongs to
  4. gives every member of the group that project

Groups whose members already sit in two or more different projects are left alone and counted
as conflicts, because one account number can really serve several projects (a checking account
pays for a mortgage and a tax bill). A group the model cannot place stays as it was.

Writes assignments-linked.json (or --out) and link-report.md for you to read. The report has
file names and only the last four characters of each identifier. The terminal gets counts.

Options:
  --out FILE        linked assignments (default: assignments-linked.json beside the input)
  --report FILE     the report for you (default: link-report.md beside the input)
  --top-level       only the folder's direct files, as in assign_projects.py
  --max-share N     ignore identifiers found in more than N files (default 12)
  --base-url, --model   the local model server, as in assign_projects.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
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
LABEL = r"(?:account|acct|loan|policy|claim|case|reference|ref|member|customer|confirmation|application|certificate)"
PATTERN = re.compile(LABEL + r"\s*(?:number|no\.?|num\.?|#|id)?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{4,28})", re.IGNORECASE)


def extract_identifiers(text: str) -> set[str]:
    """Identifiers that follow a keyword. Only those with enough digits to be a real number."""
    found = set()
    for match in PATTERN.finditer(text):
        raw = match.group(1)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):  # a date, not an account
            continue
        value = raw.replace("-", "").upper()
        if len(value) >= 6 and sum(ch.isdigit() for ch in value) >= 5:
            found.add(value)
    return found


def link_groups(ids_by_file: dict[str, set[str]], max_share: int = 12) -> list[list[str]]:
    """Connected groups of two or more files that share an identifier."""
    holders: dict[str, set[str]] = defaultdict(set)
    for name, ids in ids_by_file.items():
        for ident in ids:
            holders[ident].add(name)
    parent = {name: name for name in ids_by_file}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for files in holders.values():
        if 2 <= len(files) <= max_share:
            first, *rest = sorted(files)
            for other in rest:
                parent[find(other)] = find(first)
    groups: dict[str, list[str]] = defaultdict(list)
    for name in ids_by_file:
        groups[find(name)].append(name)
    return [sorted(members) for members in groups.values() if len(members) > 1]


def apply_links(assigned: dict, groups: list[list[str]], ask: Callable[[list[str]], str]):
    """Return (new assignments, summary, details). `ask(members)` names the group's project."""
    new = {name: {**value, "also": list(value["also"])} for name, value in assigned.items()}
    summary = {"groups": len(groups), "already_agree": 0, "conflicts": 0, "unplaced": 0, "regrouped": 0,
               "files_changed": 0}
    details = []
    for members in groups:
        members = [m for m in members if m in assigned]
        if len(members) < 2:
            continue
        before = [assigned[m]["primary"] for m in members]
        projects = set(before) - {UNSORTED}
        if len(projects) >= 2:
            summary["conflicts"] += 1
            details.append({"members": members, "before": before, "after": None, "note": "conflict, left alone"})
            continue
        if len(projects) == 1 and UNSORTED not in before:
            summary["already_agree"] += 1
            continue
        answer = ask(members)
        if answer == UNSORTED:
            summary["unplaced"] += 1
            details.append({"members": members, "before": before, "after": None, "note": "model could not place the group"})
            continue
        summary["regrouped"] += 1
        for member in members:
            if new[member]["primary"] != answer:
                summary["files_changed"] += 1
            new[member]["primary"] = answer
            new[member]["also"] = [a for a in new[member]["also"] if a != answer]
        details.append({"members": members, "before": before, "after": answer, "note": "regrouped"})
    return new, summary, details


def model_asker(folder: Path, projects: list[dict], base_url: str, model: str) -> Callable[[list[str]], str]:
    names = [p["name"] for p in projects]
    system = (assign.build_system(projects)
              + "\n\nThe files below share an account, loan, claim or case number, so they come from the same "
                "account or case. Decide the ONE project they all belong to, judging from all of them together.")
    schema = assign.build_schema(names)

    def ask(members: list[str]) -> str:
        parts = []
        for i, rel in enumerate(members[:5], 1):
            parts.append(f"File {i}: {Path(rel).name}\n{local.read_head(folder / rel, 700)}")
        answer = local.classify(base_url, model, "", "", system=system, schema=schema, user="\n\n".join(parts))
        return assign.clean(answer, names)["primary"]

    return ask


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("projects", type=Path)
    ap.add_argument("assignments", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--report", type=Path)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--max-share", type=int, default=12)
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="classifier")
    args = ap.parse_args()
    for needed in (args.folder, args.projects, args.assignments):
        if not needed.exists():
            sys.exit(f"Not found: {needed}")

    assigned = json.loads(args.assignments.read_text())
    projects = assign.load_projects(args.projects)
    ids_by_file = {}
    for rel in assigned:
        path = args.folder / rel
        if path.is_file():
            ids_by_file[rel] = extract_identifiers(local.read_head(path, 20000))
    groups = link_groups(ids_by_file, args.max_share)
    new, summary, details = apply_links(
        assigned, groups, model_asker(args.folder, projects, args.base_url, args.model))

    out = args.out or args.assignments.with_name("assignments-linked.json")
    out.write_text(json.dumps(new, indent=2))
    lines = ["# Link report", "",
             "Files that share an account, loan, claim or case number, and what was decided for each group.", ""]
    for number, item in enumerate(details, 1):
        lines.append(f"## Group {number}: {item['note']}")
        for member, before in zip(item["members"], item["before"]):
            lines.append(f"- {member}  (was: {before})")
        if item["after"]:
            lines.append(f"- all now: {item['after']}")
        lines.append("")
    report = args.report or args.assignments.with_name("link-report.md")
    report.write_text("\n".join(lines) + "\n")
    s = summary
    print(f"files scanned: {len(ids_by_file)} | linked groups: {s['groups']} | already agreed: {s['already_agree']} | "
          f"regrouped: {s['regrouped']} ({s['files_changed']} files changed) | conflicts left alone: {s['conflicts']} | "
          f"unplaced: {s['unplaced']}")
    print(f"wrote {out.name} and {report.name}")


if __name__ == "__main__":
    main()
