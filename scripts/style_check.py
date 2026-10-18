"""A deterministic style check for the book's markdown. Same file in, same findings out.

    python3 scripts/style_check.py <file-or-folder>... [--chapters]

Finds what a script can find: em dashes, inflated words, hollow intensifiers, filler openers, bold lead-ins, list labels that
end in a period, a possibly missing serial comma, Title Case headings, very long paragraphs, and (with --chapters) a chapter
README that lacks a Common tasks table or Exercises. It does not judge whether the writing is good. That is the editor's job.
Code blocks are skipped, and so is anything between `<!-- style:off -->` and `<!-- style:on -->` (for quoting the patterns). Exit status 1 when anything is found, 0 when clean.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

INFLATED = ["delve", "tapestry", "robust", "comprehensive", "seamless", "seamlessly", "leverage", "leveraging", "utilize", "pivotal",
            "testament to", "game-changer", "cutting-edge", "holistic", "streamline", "ever-evolving", "unlock", "in order to",
            "serves as", "boasts", "paradigm", "synergy", "myriad", "plethora"]
INTENSIFIERS = ["genuinely", "truly", "quite frankly", "to be honest", "it's worth noting", "it is worth noting", "it is important to note",
                "it's important to note", "needless to say", "at the end of the day"]
FILLER = ["moreover", "furthermore", "additionally", "in conclusion", "in summary", "let's dive", "let's explore", "let's take a look",
          "when it comes to"]
SERIAL = re.compile(r"\b[\w'-]+, [\w'-]+ (and|or) [\w'-]+")
SMALL = {"a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "vs", "at", "by", "from", "is", "not", "as", "it", "up"}


def prose_lines(text: str):
    """(line number, text) for lines outside code fences."""
    fenced = off = False
    for number, line in enumerate(text.splitlines(), 1):
        if "<!-- style:off -->" in line:
            off = True
        elif "<!-- style:on -->" in line:
            off = False
        elif line.strip().startswith("```"):
            fenced = not fenced
        elif not fenced and not off:
            yield number, line


def check_text(text: str, name: str = "", chapter: bool = False) -> list[tuple[str, int, str, str]]:
    found: list[tuple[str, int, str, str]] = []

    def add(line, rule, detail):
        found.append((name, line, rule, detail[:90]))

    paragraph: list[str] = []
    start = 0

    def flush():
        words = sum(len(p.split()) for p in paragraph)
        if words > 130 and not paragraph[0].lstrip().startswith(("|", "-", "*", ">", "1", "2", "3")):
            add(start, "long-paragraph", f"{words} words")
        paragraph.clear()

    for number, line in prose_lines(text):
        stripped = line.strip()
        if not stripped:
            if paragraph:
                flush()
            continue
        if not paragraph:
            start = number
        paragraph.append(stripped)
        if stripped.startswith("|"):
            continue  # tables: only the paragraph-length check was skipped above; word rules still apply below
        lower = stripped.lower()
        if "—" in stripped or " -- " in stripped:
            add(number, "em-dash", stripped)
        for word in INFLATED:
            if re.search(rf"\b{re.escape(word)}\b", lower):
                add(number, "inflated-word", word)
        for phrase in INTENSIFIERS + FILLER:
            if phrase in lower:
                add(number, "filler", phrase)
        if re.match(r"\*\*[^*]+\*\*\s", stripped) and not stripped.startswith(("- ", "* ")) and not re.match(r"\d+\.", stripped):
            add(number, "bold-lead-in", stripped)
        if re.match(r"([-*]|\d+\.)\s+\*\*[^*:]+\.\*\*", stripped):
            add(number, "list-label-period", stripped)
        if SERIAL.search(stripped) and not stripped.startswith(("|", "#")) and "`" not in stripped:
            add(number, "serial-comma?", SERIAL.search(stripped).group(0))
        if stripped.startswith("#"):
            title = stripped.lstrip("#").strip()
            words = [w for w in re.findall(r"[A-Za-z][A-Za-z'-]*", title)]
            caps = [w for w in words[1:] if w[0].isupper() and w.lower() not in SMALL]
            if len(words) >= 4 and len(caps) >= 3 and not re.match(r"^(Chapter|Listing|Figure|\d)", title):
                add(number, "title-case-heading", title)
    if paragraph:
        flush()
    if chapter:
        for needed in ("Common tasks", "Exercises"):
            if not re.search(rf"^#+\s+.*{needed}", text, re.M | re.I):
                found.append((name, 0, "missing-section", needed))
    return found


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--chapters", action="store_true", help="also require Common tasks and Exercises in chapter READMEs")
    args = ap.parse_args()
    files: list[Path] = []
    for raw in args.paths:
        path = Path(raw)
        files += sorted(path.rglob("*.md")) if path.is_dir() else [path]
    total = 0
    for path in files:
        is_chapter = args.chapters and path.name == "README.md" and "chapters" in path.parts
        for name, line, rule, detail in check_text(path.read_text(), str(path), is_chapter):
            print(f"{name}:{line}: {rule}: {detail}")
            total += 1
    print(f"{total} finding(s) in {len(files)} file(s).")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
