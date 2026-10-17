"""Assign each file to one of YOUR projects, using a model on your own machine.

    python3 assign_projects.py <folder> <projects.json> [options]

projects.json is a list you write: [{"name": "Kitchen remodel", "description": "..."}, ...].
For every file the local model sees the file name, the website it was downloaded from (macOS
records this), the date it was last modified, and the start of its contents. It answers:

  primary      the one project the file mainly belongs to, or "Unsorted"
  also         up to two other projects the file clearly serves (usually none)
  sensitivity  the same data-loss-prevention label as Chapter 1B

The answer can only be a project name from your list, because the server limits the model to
an enum built from it. The model cannot write free text, so file contents cannot leak through
its output. Output: assignments.json beside <folder>, for plan_projects.py.

Options:
  --base-url URL   OpenAI-compatible server (default LM Studio, http://localhost:1234/v1)
  --model NAME     model identifier (default: classifier)
  --out FILE       where to write assignments.json
  --top-level      only the folder's direct files; subfolders are never opened
  --no-source      hide the download website from the model (for experiments)
  --no-dates       hide the modified date from the model (for experiments)
  --verbose        print file names as it goes (off by default, so logs hold no names)
"""
from __future__ import annotations

import argparse
import datetime
import json
import plistlib
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

CH1 = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
import classify_local as local  # noqa: E402

UNSORTED = "Unsorted"
FORBIDDEN_IN_NAMES = "/|;\\"

SENSITIVITY_HELP = """sensitivity, data-loss-prevention view: what kind of sensitive data the file holds.
none = nothing sensitive. personal = resumes, contact details, private letters.
financial = invoices, bank, tax, budgets. health = medical. credentials = passwords, keys.
government_id = SSN, passport, tax IDs, W-2. legal = leases, contracts.
If unsure whether something is sensitive, pick the sensitive kind, not none."""


def load_projects(path: Path) -> list[dict]:
    projects = json.loads(path.read_text())
    names = [p["name"] for p in projects]
    if len(set(names)) != len(names):
        sys.exit("Project names must be unique.")
    for name in names:
        if not name.strip() or name == UNSORTED or any(ch in name for ch in FORBIDDEN_IN_NAMES):
            sys.exit(f"Bad project name {name!r}: it must be non-empty, not '{UNSORTED}', "
                     f"and contain none of {FORBIDDEN_IN_NAMES!r}")
    return projects


def download_domain(path: Path) -> str | None:
    """The website a file was downloaded from, if macOS recorded one. Only the host is kept."""
    if sys.platform != "darwin":
        return None
    done = subprocess.run(["xattr", "-px", "com.apple.metadata:kMDItemWhereFroms", str(path)],
                          capture_output=True, text=True)
    if done.returncode != 0:
        return None
    try:
        values = plistlib.loads(bytes.fromhex("".join(done.stdout.split())))
    except Exception:
        return None
    for value in values:
        host = urlparse(str(value)).netloc
        if host:
            return host
    return None


def build_schema(names: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "primary": {"type": "string", "enum": names + [UNSORTED]},
            "also": {"type": "array", "items": {"type": "string", "enum": names}, "maxItems": 2},
            "sensitivity": {"type": "string", "enum": local.SENSITIVITIES},
        },
        "required": ["primary", "also", "sensitivity"],
        "additionalProperties": False,
    }


def build_system(projects: list[dict]) -> str:
    listing = "\n".join(f"- {p['name']}: {p.get('description', '')}".rstrip(": ") for p in projects)
    return f"""You file downloaded documents into the user's projects.

The projects:
{listing}

For each file you get its name, the website it was downloaded from (if known), the date it was
last modified, and the start of its contents. Answer with JSON.

primary: the one project the file mainly belongs to. Use {UNSORTED} if no project clearly fits or
you cannot tell. A topic that none of the project descriptions mentions belongs in {UNSORTED}, even
when one project is loosely related. Being nearby is not enough: a recipe does not belong in a
fitness project just because both involve food.
also: up to two OTHER projects the file clearly serves as well. Usually this is empty.
{SENSITIVITY_HELP}

Files from the same website, or modified within days of each other, often belong to the same
project. Many documents mention the same person and address, which says nothing about the
project. Decide by what the document is about."""


def build_user(name: str, domain: str | None, modified: str, head: str,
               use_source: bool, use_dates: bool) -> str:
    lines = [f"File name: {name}"]
    if use_source:
        lines.append(f"Downloaded from: {domain or 'unknown'}")
    if use_dates:
        lines.append(f"Last modified: {modified}")
    return "\n".join(lines) + f"\n\nContent start:\n{head}"


def clean(answer: dict, names: list[str]) -> dict:
    """Never trust the shape of a model's answer, even a schema-constrained one."""
    primary = answer.get("primary") if answer.get("primary") in names else UNSORTED
    also = []
    for item in answer.get("also", []):
        if item in names and item != primary and item not in also:
            also.append(item)
    sensitivity = answer.get("sensitivity")
    if sensitivity != "none" and sensitivity not in local.SENSITIVITIES:
        sensitivity = "unknown"  # fail closed
    return {"primary": primary, "also": also[:2], "sensitivity": sensitivity}


class AppleHelper:
    """Apple's on-device model, reached through the assign_apple helper (see assign_apple.swift)."""

    def __init__(self, helper: Path, names: list[str], system: str):
        self.names, self.system = names, system
        self.process = subprocess.Popen([str(helper)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, text=True)

    def classify(self, user: str) -> dict:
        request = {"system": self.system, "user": user, "projects": self.names,
                   "sensitivities": local.SENSITIVITIES}
        self.process.stdin.write(json.dumps(request) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("the Apple helper stopped (is Apple Intelligence on?)")
        answer = json.loads(line)
        if "error" in answer:
            raise RuntimeError(answer["error"][:80])
        return answer


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("projects", type=Path)
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="classifier")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--no-source", action="store_true")
    ap.add_argument("--no-dates", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", type=Path, metavar="FILE",
                    help="a JSON list of relative paths; assign only those files (used by sweep.py)")
    ap.add_argument("--apple", type=Path, metavar="HELPER",
                    help="use Apple's on-device model through the compiled assign_apple helper "
                         "instead of a local server (macOS 26+, Apple Intelligence on)")
    ap.add_argument("--max-tokens", type=int, default=200,
                    help="longest answer to allow; models that think first may need more (default 200)")
    args = ap.parse_args()
    if not args.folder.is_dir():
        sys.exit(f"Not a folder: {args.folder}")
    if not args.projects.is_file():
        sys.exit(f"Project list not found: {args.projects}")

    projects = load_projects(args.projects)
    names = [p["name"] for p in projects]
    system, schema = build_system(projects), build_schema(names)
    out = args.out or args.folder.resolve().parent / "assignments.json"
    candidates = args.folder.iterdir() if args.top_level else args.folder.rglob("*")
    # In top-level mode, hidden files are left alone: they belong to the system or to applications.
    files = sorted(p for p in candidates if p.is_file() and p.name != ".DS_Store"
                   and not (args.top_level and p.name.startswith(".")))

    apple = AppleHelper(args.apple, names, system) if args.apple else None
    if args.only:
        wanted = set(json.loads(args.only.read_text()))
        files = [p for p in files if str(p.relative_to(args.folder)) in wanted]
    results, failed = {}, 0
    for i, path in enumerate(files, 1):
        rel = str(path.relative_to(args.folder))
        modified = datetime.datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()
        user = build_user(path.name, download_domain(path), modified, local.read_head(path),
                          not args.no_source, not args.no_dates)
        try:
            answer = apple.classify(user) if apple else local.classify(
                args.base_url, args.model, path.name, "", system=system,
                schema=schema, user=user, max_tokens=args.max_tokens)
            results[rel] = clean(answer, names)
        except Exception as err:  # fail closed: plan_projects files a missing answer under Unsorted
            failed += 1
            print(f"  ! item {i}: {type(err).__name__}")
            continue
        shown = rel if args.verbose else f"item {i}"
        print(f"[{i}/{len(files)}] {shown}: {results[rel]['primary']}")
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out.name}: {len(results)} of {len(files)} files assigned, {failed} failed.")


if __name__ == "__main__":
    main()
