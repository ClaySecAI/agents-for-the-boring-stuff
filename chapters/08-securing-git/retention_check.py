#!/usr/bin/env python3
"""Check that every repository you own keeps CI artifacts and logs for the same short time (section 8.7).

    python3 retention_check.py [--owner NAME] [--days 7]            # read-only report
    python3 retention_check.py [--owner NAME] [--days 7] --apply    # set the ones that differ

GitHub has no default for a personal account, so a new repository starts at 90 days. Artifacts and run logs
become public with a repository, so the shorter they live the less a mistake costs. This reads each repository's
setting through the `gh` command (signed in as you). Without `--apply` it changes nothing. With it, it sets only
the retention days, one repository at a time, and reads each setting back to confirm.

It does not delete existing artifacts or logs. A new setting only shortens what is stored from then on.

Exit codes: 0 every repository is at the target, 1 at least one is not (or could not be read or set), 2 it could not run.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import subprocess
import sys
from typing import List, Optional, Sequence

DEFAULT_DAYS = 7
PATH = "repos/{owner}/{name}/actions/permissions/artifact-and-log-retention"


@dataclasses.dataclass
class Row:
    name: str
    status: str  # OK, DIFFERS, FIXED, SKIP, FAIL
    detail: str


class GhApi:
    """Reads and sets the retention days through `gh api`. Returns None on any error."""

    def _run(self, args: Sequence[str]) -> Optional[str]:
        try:
            done = subprocess.run(["gh", *args], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return None
        return done.stdout if done.returncode == 0 else None

    def whoami(self) -> Optional[str]:
        out = self._run(["api", "user", "--jq", ".login"])
        return out.strip() if out else None

    def repos(self, owner: str) -> Optional[List[dict]]:
        out = self._run(["repo", "list", owner, "--limit", "1000", "--json", "name,isArchived,isFork"])
        try:
            return json.loads(out) if out else None
        except ValueError:
            return None

    def get_days(self, owner: str, name: str) -> Optional[int]:
        out = self._run(["api", PATH.format(owner=owner, name=name)])
        try:
            days = json.loads(out)["days"] if out else None
        except (ValueError, KeyError, TypeError):
            return None
        return days if isinstance(days, int) else None

    def set_days(self, owner: str, name: str, days: int) -> bool:
        return self._run(["api", "-X", "PUT", PATH.format(owner=owner, name=name), "-F", f"days={days}"]) is not None


def check(api, owner: str, days: int, apply: bool = False) -> List[Row]:
    repos = api.repos(owner)
    if repos is None:
        raise RuntimeError(f"could not list repositories for {owner}: is `gh` installed and signed in?")
    rows: List[Row] = []
    for repo in sorted(repos, key=lambda r: r["name"]):
        name = repo["name"]
        if repo.get("isArchived"):
            rows.append(Row(name, "SKIP", "archived: GitHub does not let you change settings"))
            continue
        current = api.get_days(owner, name)
        if current == days:
            rows.append(Row(name, "OK", f"{days} days"))
            continue
        shown = "could not be read" if current is None else f"is {current} days"
        if not apply:
            rows.append(Row(name, "DIFFERS", f"retention {shown}, target {days}"))
            continue
        if api.set_days(owner, name, days) and api.get_days(owner, name) == days:
            rows.append(Row(name, "FIXED", f"retention {shown}, now {days} days"))
        else:
            rows.append(Row(name, "FAIL", f"retention {shown}; setting {days} did not stick (need admin rights?)"))
    return rows


def exit_code(rows: Sequence[Row]) -> int:
    return 1 if any(r.status in ("DIFFERS", "FAIL") for r in rows) else 0


def main(argv: Optional[Sequence[str]] = None, api=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--owner", help="account to check (default: the account `gh` is signed in as)")
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS, help=f"target retention (default {DEFAULT_DAYS})")
    parser.add_argument("--apply", action="store_true", help="set the repositories that differ")
    args = parser.parse_args(argv)
    if not 1 <= args.days <= 90:
        print("retention_check: --days must be between 1 and 90 (the limit for public repositories)", file=sys.stderr)
        return 2
    api = api or GhApi()
    owner = args.owner or api.whoami()
    if not owner:
        print("retention_check: could not tell who you are. Run `gh auth login` or pass --owner.", file=sys.stderr)
        return 2
    try:
        rows = check(api, owner, args.days, args.apply)
    except RuntimeError as err:
        print(f"retention_check: {err}", file=sys.stderr)
        return 2
    for row in rows:
        if row.status != "OK":
            print(f"{row.status:7} {row.name}: {row.detail}")
    counts = {s: sum(1 for r in rows if r.status == s) for s in ("OK", "DIFFERS", "FIXED", "SKIP", "FAIL")}
    print(f"{owner}: {len(rows)} repositories, {counts['OK']} at {args.days} days, {counts['FIXED']} fixed, "
          f"{counts['DIFFERS']} differ, {counts['FAIL']} failed, {counts['SKIP']} skipped")
    if counts["DIFFERS"]:
        print(f"Fix: python3 chapters/08-securing-git/retention_check.py --days {args.days} --apply")
    return exit_code(rows)


if __name__ == "__main__":
    sys.exit(main())
