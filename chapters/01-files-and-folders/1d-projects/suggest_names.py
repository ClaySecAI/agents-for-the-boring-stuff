"""Suggest better file names with a local model. Nothing is renamed here.

    python3 suggest_names.py <folder> [--all] [--model NAME] [--base-url URL] [--top-level] [--out names.json]

Writes names.json, {"<path>": "<new file name>"}, which plan_projects.py --names turns into the To
column of the plan. The rename then goes through the same plan, approval, apply, verify and undo as
every move.

Names look like "2024-03-08 Lease renewal.pdf": the file's modified date, a short title the model
read from the contents, and the original extension, which never changes. By default only files whose
names say nothing are renamed (IMG_4412.jpg, scan0042.pdf, Document (3).pdf, a long run of hex digits).
A name you chose yourself, like "Resume - Clay.pdf", is left alone unless you pass --all.

Unlike the other model calls in this chapter, the model writes free text here: the title. It runs on
your machine, and the title is cleaned (characters other than letters, digits, spaces and a few
punctuation marks are dropped, length is capped) before it can become a file name. A title is also
never shown to Claude: claude-view.txt does not carry names.
"""
from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
import classify_local as local  # noqa: E402
from plan_common import IGNORED_NAMES  # noqa: E402

GENERIC = [
    r"(img|dsc|dscn|pxl|image|photo|pic|scan|scanned|document|doc|file|download|untitled|screenshot|"
    r"screen shot|attachment|new document|export)[ _\-]*\(?\d*\)?",
    r"[0-9a-f]{16,}",                      # a hash or a uuid
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    r"\d{6,}",                             # only digits
    r"(img|dsc|scan|image|photo)[ _\-]?\d{3,}.*",
    r"screen ?shot \d{4}-\d{2}-\d{2}.*",
]
SYSTEM = ("You name one file for a file-tidying tool. You get the start of its contents. Answer with JSON: "
          "a title of 2 to 6 words naming what the document IS (for example: Lease renewal, Pay stub March, "
          "Dental invoice). No dates, no file extension, no account numbers, no personal names unless the "
          "document is about that person. If the contents say nothing, answer with an empty title.")
SCHEMA = {"type": "object", "properties": {"title": {"type": "string"}},
          "required": ["title"], "additionalProperties": False}


def is_generic(filename: str) -> bool:
    stem = re.sub(r"\s*\(\d+\)$", "", Path(filename).stem.strip().lower())
    return any(re.fullmatch(p, stem) for p in GENERIC)


def clean_title(title: str, limit: int = 60) -> str:
    title = re.sub(r"[^\w .,&'+()-]", " ", title, flags=re.UNICODE)
    title = re.sub(r"[_\s]+", " ", title).strip(" .-")
    if len(title) > limit:
        title = title[:limit].rsplit(" ", 1)[0]
    return title


def build_name(title: str, modified: datetime.date, suffix: str) -> str:
    return f"{modified.isoformat()} {title}{suffix.lower()}"


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("--all", action="store_true", help="also rename files whose names are already meaningful")
    ap.add_argument("--model", default="local-model")
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    candidates = args.folder.iterdir() if args.top_level else args.folder.rglob("*")
    files = sorted(p for p in candidates if p.is_file() and p.name not in IGNORED_NAMES and not p.name.startswith("."))
    names, skipped, failed = {}, 0, 0
    for path in files:
        if not args.all and not is_generic(path.name):
            skipped += 1
            continue
        head = local.read_head(path, 1500)
        if not head.strip() or head.startswith("[binary"):
            skipped += 1
            continue
        try:
            answer = local.classify(args.base_url, args.model, path.name, head, system=SYSTEM, schema=SCHEMA,
                                    user=f"Content start:\n{head}", max_tokens=60)
        except Exception:  # noqa: BLE001 - any failure leaves the file with its old name
            failed += 1
            continue
        title = clean_title(answer.get("title", ""))
        if len(title) < 3:
            skipped += 1
            continue
        modified = datetime.date.fromtimestamp(path.stat().st_mtime)
        names[str(path.relative_to(args.folder))] = build_name(title, modified, path.suffix)
    out = args.out or args.folder.resolve().parent / "names.json"
    out.write_text(json.dumps(names, indent=2))
    print(f"{len(names)} names suggested, {skipped} left as they are, {failed} failed. wrote {out.name}")


if __name__ == "__main__":
    main()
