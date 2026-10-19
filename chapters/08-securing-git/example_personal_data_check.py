#!/usr/bin/env python3
"""A small example of the personal-data check from section 8.4. Run it from a pre-commit hook.

    python3 example_personal_data_check.py [--terms FILE]

It looks only at the lines you are about to commit (`git diff --cached`) and refuses when it finds:

  1. a whole word from your private blocklist (default: ~/.config/git/private-terms.txt, one term per line),
  2. your home folder's path,
  3. a commit email that is not a GitHub noreply address, unless `hooks.allowEmail` in the repository's
     own git config names it.

It prints the file, the line number, and the kind of problem. It never prints the text that matched, because a
terminal log is one more place for personal data to leak.

This is an example, not the author's own hook. It shows the idea in under 100 lines so you can adapt it. It does
not run gitleaks, does not call a repository's own hook, and has no opt-out for repositories meant to hold
personal data. The dispatcher in 8.4 adds those.

Exit codes: 0 nothing found, 1 something found, 2 it could not run.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

DEFAULT_TERMS = Path.home() / ".config" / "git" / "private-terms.txt"
NOREPLY_SUFFIX = "@users.noreply.github.com"


def git(*args: str) -> Optional[str]:
    done = subprocess.run(["git", *args], capture_output=True, text=True, stdin=subprocess.DEVNULL)
    return done.stdout if done.returncode == 0 else None


def load_terms(path: Path) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    return [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]


def added_lines(diff: str) -> List[Tuple[str, int, str]]:
    """(file, line number, text) for each added line in a zero-context diff."""
    found: List[Tuple[str, int, str]] = []
    name, number = "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            name = raw[4:].removeprefix("b/")
        elif raw.startswith("@@"):
            match = re.search(r"\+(\d+)", raw)
            number = int(match.group(1)) if match else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            found.append((name, number, raw[1:]))
            number += 1
    return found


def check_lines(lines: Sequence[Tuple[str, int, str]], terms: Sequence[str], home: str) -> List[str]:
    patterns = [re.compile(r"(?<!\w)" + re.escape(term) + r"(?!\w)", re.IGNORECASE) for term in terms]
    problems: List[str] = []
    for name, number, text in lines:
        if any(p.search(text) for p in patterns):
            problems.append(f"{name}:{number}: a term from your blocklist")
        if home and home in text:
            problems.append(f"{name}:{number}: your home folder path")
    return problems


def check_email() -> Optional[str]:
    email = (git("config", "user.email") or "").strip()
    allowed = (git("config", "--local", "hooks.allowEmail") or "").strip()
    if email.endswith(NOREPLY_SUFFIX) or (allowed and email == allowed):
        return None
    return "the commit email is not a GitHub noreply address (set one with: git config user.email <id>+<name>" + NOREPLY_SUFFIX + ")"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--terms", type=Path, default=DEFAULT_TERMS, help="blocklist file, one term per line")
    args = parser.parse_args(argv)
    diff = git("diff", "--cached", "-U0", "--no-color", "--no-ext-diff")
    if diff is None:
        print("example_personal_data_check: could not read the staged changes. Run it inside a repository.", file=sys.stderr)
        return 2
    problems = check_lines(added_lines(diff), load_terms(args.terms), str(Path.home()))
    email_problem = check_email()
    if email_problem:
        problems.append(email_problem)
    for problem in problems:
        print(f"BLOCKED {problem}")
    if problems:
        print("Fix the lines above. A deliberate exception is a `git commit --no-verify`, and that is your call.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
