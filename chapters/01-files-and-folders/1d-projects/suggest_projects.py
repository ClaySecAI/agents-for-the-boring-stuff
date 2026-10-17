"""Suggest a starting project list from your files. A draft to edit, not a replacement for your list.

    python3 suggest_projects.py <folder> [options]

Two local-model steps:

  1. For each file, the model writes a short phrase for the real-life situation it belongs to
     ("buying a car", "filing a tax return"). These phrases are free text and stay on your machine,
     in topics.json beside the folder.
  2. One call reads all the phrases and proposes a handful of projects, each with a name and a
     one-sentence description, in the same shape as projects.json.

Edit the result, then use it as the list for assign_projects.py. Section 1D.3 of the chapter explains
why you should edit it: the model proposes from what is in the folder, and only you know which efforts
matter, what to call them, and where one ends and the next begins.

Options:
  --framing projects|none   projects (default) tells the model to think in purchases, trips, cases and
                            other efforts, and not in kinds of document. none gives it no such steer;
                            it exists so the experiment in the chapter can show the difference
  --max-projects N          most projects to propose (default 10)
  --top-level               only the folder's direct files; subfolders are never opened
  --out FILE                where to write the suggestions (default: projects-suggested.json beside the folder)
  --show                    print the proposed names (off by default: names describe your files)
  --base-url, --model       the local model server, as in assign_projects.py
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
sys.path.insert(0, str(HERE))
import assign_projects as assign  # noqa: E402
import classify_local as local  # noqa: E402

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"topic": {"type": "string"}},
    "required": ["topic"],
    "additionalProperties": False,
}

TOPIC_SYSTEM = {
    "projects": ("You describe what real-life situation a downloaded document belongs to. In at most 8 words, "
                 "name the purchase, event, case or effort it is part of, for example 'buying a car' or "
                 "'filing a tax return'. Do not name the kind of document."),
    "none": "In at most 8 words, say what this document is about.",
}

PROJECT_SYSTEM = {
    "projects": ("Below are one-line descriptions of the files in someone's Downloads folder. Propose the "
                 "real-life projects or efforts these files belong to: a purchase, a trip, a job search, a "
                 "repair, a legal or insurance case, a training plan. Each project is a set of files that "
                 "belong together. Do NOT propose categories by kind of document, such as invoices, "
                 "receipts, PDFs or spreadsheets. Give each project a short name and a one-sentence "
                 "description naming the kinds of documents it holds. If many files are installers or "
                 "software updates, propose one project for them."),
    "none": ("Below are one-line descriptions of the files in someone's Downloads folder. Propose "
             "categories to organize the files into. Give each category a short name and a one-sentence "
             "description."),
}


def projects_schema(limit: int) -> dict:
    item = {"type": "object",
            "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
            "required": ["name", "description"], "additionalProperties": False}
    return {"type": "object",
            "properties": {"projects": {"type": "array", "items": item, "maxItems": limit}},
            "required": ["projects"], "additionalProperties": False}


def sanitize(raw: list[dict], limit: int) -> list[dict]:
    """Keep only names that assign_projects.py will accept: no separators, unique, not 'Unsorted'."""
    clean, seen = [], set()
    for item in raw:
        stripped = "".join(ch for ch in str(item.get("name", "")) if ch not in assign.FORBIDDEN_IN_NAMES)
        name = " ".join(stripped.split()).strip(".")  # collapse the gaps that removed characters leave
        if not name or name == assign.UNSORTED or name.lower() in seen:
            continue
        seen.add(name.lower())
        clean.append({"name": name, "description": str(item.get("description", "")).strip()})
    return clean[:limit]


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--framing", choices=["projects", "none"], default="projects")
    ap.add_argument("--max-projects", type=int, default=10)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="classifier")
    args = ap.parse_args()
    if not args.folder.is_dir():
        sys.exit(f"Not a folder: {args.folder}")

    candidates = args.folder.iterdir() if args.top_level else args.folder.rglob("*")
    files = sorted(p for p in candidates if p.is_file() and p.name != ".DS_Store")
    topics = {}
    for i, path in enumerate(files, 1):
        modified = datetime.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        user = assign.build_user(path.name, assign.download_domain(path), modified, local.read_head(path), True, True)
        try:
            answer = local.classify(args.base_url, args.model, path.name, "", system=TOPIC_SYSTEM[args.framing],
                                    schema=TOPIC_SCHEMA, user=user)
            topics[str(path.relative_to(args.folder))] = str(answer.get("topic", "")).strip()
        except Exception as err:
            print(f"  ! item {i}: {type(err).__name__}")
    parent = args.folder.resolve().parent
    (parent / "topics.json").write_text(json.dumps(topics, indent=2))
    print(f"topics written for {len(topics)} of {len(files)} files")

    listing = "\n".join(f"- {t}" for t in sorted(topics.values()) if t)
    user = f"Files:\n{listing}\n\nPropose at most {args.max_projects}."
    answer = local.classify(args.base_url, args.model, "", "", system=PROJECT_SYSTEM[args.framing],
                            schema=projects_schema(args.max_projects), user=user, max_tokens=2500)
    proposed = sanitize(answer.get("projects", []), args.max_projects)
    out = args.out or parent / "projects-suggested.json"
    out.write_text(json.dumps(proposed, indent=2))
    print(f"{len(proposed)} projects proposed ({args.framing} framing) -> {out.name}")
    if args.show:
        for item in proposed:
            print(f"  {item['name']}: {item['description']}")


if __name__ == "__main__":
    main()
