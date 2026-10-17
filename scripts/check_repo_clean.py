"""Block personal data from reaching git (and therefore GitHub).

    python3 scripts/check_repo_clean.py --staged   # what the pre-commit hook runs
    python3 scripts/check_repo_clean.py --all      # everything git could pick up (tracked + untracked)

.gitignore only *asks* git to skip files. `git add -f` overrides it. This guard is the
second layer: it looks at what is actually about to be committed and refuses if

  1. a file isn't on the ALLOWLIST (this repo holds docs, source and one settings file,
     nothing else; binaries, JSON labels, plans, snapshots and any "practice" folder are out),
  2. a file is suspiciously large,
  3. a text file contains something personal-looking: a home-directory path, an email
     address, an SSN-shaped number, a key or token,
  4. a text file contains a term from your private blocklist: `.git/private-terms.txt`,
     one term per line, case-insensitive. It lives inside .git, so it is never committed.
     Put your name, username, employer, and names of real files you tested with in there.

Matches are reported as file and line number only. The matched text is never printed.
"""
from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path

ALLOW = ["*.md", "*.py", "*.swift", "LICENSE", ".gitignore", ".claude/settings.json",
         ".githooks/pre-commit", ".github/workflows/*.yml"]
# Even an allowed extension is refused if the NAME says it is generated data.
DENY_NAMES = ["classification*", "claude-view*", "organize-plan*", ".*manifest*", ".*applied-plan*",
              ".*undone-plan*", ".DS_Store", "assignments*", "protect-list*", "truth*", "projects.json",
              "link-report*", "review*.md", "topics*", "projects-suggested*", "rules*.json", "corrections*.json", "names*.json", "bakeoff-results*"]
DENY_DIRS = ["practice"]  # any path segment that starts with this
MAX_BYTES = 200 * 1024

FIXED_PATTERNS = {
    "a home-directory path": re.compile(r"(/Users/[^/\s]+|/home/[A-Za-z0-9_.-]+|[A-Za-z]:\\Users\\)"),
    "an email address": re.compile(r"\b[A-Za-z0-9._%+-]+@(?!example\.(com|org)|users\.noreply\.github\.com|anthropic\.com)"
                                   r"[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    "an SSN-shaped number": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "an API key or token": re.compile(r"(sk-[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}"
                                      r"|-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
}


def git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout


def private_terms() -> list[str]:
    path = Path(git("rev-parse", "--git-dir").strip()) / "private-terms.txt"
    if not path.is_file():
        return []
    return [t.strip().lower() for t in path.read_text().splitlines() if t.strip() and not t.startswith("#")]


def allowed(path: str) -> bool:
    return any(fnmatch.fnmatch(path, pattern) for pattern in ALLOW)


def check_path(path: str) -> list[str]:
    problems = []
    name = Path(path).name
    if any(part.startswith(prefix) for part in Path(path).parts for prefix in DENY_DIRS):
        problems.append("is inside a practice folder (test data, possibly your real files)")
    if any(fnmatch.fnmatch(name, pattern) for pattern in DENY_NAMES):
        problems.append("looks like generated output (labels, plan, snapshot or OS metadata)")
    if not allowed(path):
        problems.append("is not on the allowlist (docs, source and one settings file only)")
    return problems


# These two files must spell out the very patterns they look for (a regex for home paths, a
# planted fake email in a test), so the pattern scan skips them. The private blocklist and the
# size limit still apply, and they are still subject to the allowlist.
PATTERN_SCAN_EXEMPT = {"scripts/check_repo_clean.py", "scripts/test_check_repo_clean.py"}


def check_content(path: str, data: bytes, terms: list[str]) -> list[tuple[int, str]]:
    if b"\x00" in data:
        return [(0, "is a binary file")]
    found = []
    for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
        lowered = line.lower()
        for label, pattern in ({} if path in PATTERN_SCAN_EXEMPT else FIXED_PATTERNS).items():
            if pattern.search(line):
                found.append((number, f"contains {label}"))
        if any(term in lowered for term in terms):
            found.append((number, "contains a term from your private blocklist"))
    return found


def main(staged: bool) -> int:
    terms = private_terms()
    if staged:
        paths = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").split("\0")
    else:
        paths = git("ls-files", "-co", "--exclude-standard", "-z").split("\0")
    paths = [p for p in paths if p]
    failures = []
    for path in paths:
        for reason in check_path(path):
            failures.append(f"  {path}: {reason}")
        if staged:
            data = subprocess.run(["git", "show", f":{path}"], capture_output=True).stdout
        else:
            file = Path(path)
            data = file.read_bytes() if file.is_file() else b""
        if len(data) > MAX_BYTES:
            failures.append(f"  {path}: is {len(data) // 1024} KB (limit {MAX_BYTES // 1024} KB)")
        for number, reason in check_content(path, data, terms):
            where = f"line {number}" if number else "file"
            failures.append(f"  {path}: {where} {reason}")
    if failures:
        print(f"BLOCKED: {len(failures)} problem(s) found in {len(paths)} file(s). Nothing was committed.")
        print("\n".join(failures))
        print("\nFix or unstage the files above. (Matched text is never printed, only where it is.)")
        return 1
    note = "" if terms else " (no private blocklist set: add terms to .git/private-terms.txt)"
    print(f"Clean: {len(paths)} file(s) checked{note}.")
    return 0


if __name__ == "__main__":
    if sys.argv[1:] not in (["--staged"], ["--all"]):
        sys.exit(__doc__)
    sys.exit(main(staged=sys.argv[1] == "--staged"))
