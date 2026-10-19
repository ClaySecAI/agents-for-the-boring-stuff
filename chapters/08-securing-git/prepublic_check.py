#!/usr/bin/env python3
"""Check a GitHub repository against the pre-public checklist (section 8.7). Read-only.

    python3 prepublic_check.py <path to a local clone> [--repo owner/name]

It asks GitHub through the `gh` command (signed in as you) and reads the clone's files. It changes nothing,
anywhere. Each check prints PASS, WARN, FAIL, or SKIP with the fix beside it:

  1. the history audit ran on this repository since its last commit (audit_history.py),
  2. secret scanning and push protection are on,
  3. private vulnerability reporting is on,
  4. the default branch blocks force pushes and deletion,
  5. no required check can be skipped by a workflow path filter (a skipped required check blocks the pull request forever),
  6. the community files exist: security policy, contributing guide, code of conduct, issue and pull request templates,
  7. CI has not stored artifacts (they are public when the repository is),
  8. a signed-out request sees the repository the way you expect.

On a private repository, items 2 to 4 are WARN, not FAIL: a free plan offers them only once the repository is public.
Turn them on at once after you flip it.

Exit codes: 0 no FAIL, 1 at least one FAIL, 2 it could not run.
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Optional

REPORT_DIR = Path.home() / ".local" / "share" / "history-audit"
COMMUNITY = [
    ("security policy", ["SECURITY.md", ".github/SECURITY.md"]),
    ("contributing guide", ["CONTRIBUTING.md", ".github/CONTRIBUTING.md"]),
    ("code of conduct", ["CODE_OF_CONDUCT.md", ".github/CODE_OF_CONDUCT.md"]),
    ("issue templates", [".github/ISSUE_TEMPLATE"]),
    ("pull request template", ["pull_request_template.md", ".github/pull_request_template.md"]),
]


@dataclasses.dataclass
class Result:
    status: str   # PASS, WARN, FAIL, SKIP
    name: str
    detail: str
    fix: str = ""


class GhApi:
    """GET requests through `gh api`. Returns parsed JSON, or None for a 404, a 403, or any error."""

    def get(self, path: str) -> Optional[object]:
        try:
            done = subprocess.run(["gh", "api", path], capture_output=True, text=True, timeout=60,
                                  stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return None
        if done.returncode != 0:
            return None
        try:
            return json.loads(done.stdout)
        except ValueError:
            return None


def signed_out_status(url: str) -> int:
    """The HTTP status of an unauthenticated request."""
    req = urllib.request.Request(url, headers={"User-Agent": "prepublic-check"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code
    except OSError:
        return 0


def repo_from_remote(clone: Path) -> Optional[str]:
    url = subprocess.run(["git", "-C", str(clone), "remote", "get-url", "origin"],
                         capture_output=True, text=True).stdout.strip()
    match = re.match(r"(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
                     r"([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return match.group(1) if match else None


def severity(public: bool) -> str:
    return "FAIL" if public else "WARN"


# --- the checks --------------------------------------------------------------------------------------

def check_history_audit(clone: Path, report_dir: Path) -> Result:
    name = "history audit"
    fix = f"python3 chapters/08-securing-git/audit_history.py audit {clone}"
    head = subprocess.run(["git", "-C", str(clone), "log", "-1", "--format=%ct"], capture_output=True, text=True).stdout.strip()
    reports = sorted(report_dir.glob(f"{clone.resolve().name}-*.json"), key=lambda p: p.stat().st_mtime) if report_dir.is_dir() else []
    if not reports:
        return Result("FAIL", name, "no audit report for this repository", fix)
    latest = reports[-1]
    if head and latest.stat().st_mtime < int(head):
        return Result("FAIL", name, "the newest audit report is older than the last commit", fix)
    try:
        hits = json.loads(latest.read_text())["counts"]["hits"]
    except (ValueError, KeyError, OSError):
        return Result("FAIL", name, "the newest audit report cannot be read", fix)
    if hits:
        return Result("WARN", name, f"{hits} hit(s) in {latest.name}; each needs a decision from you", f"audit_history.py show {clone} <id>")
    return Result("PASS", name, f"{latest.name}: no hits")


def check_scanning(info: dict, public: bool) -> list:
    sec = info.get("security_and_analysis") or {}
    out = []
    for label, key in (("secret scanning", "secret_scanning"), ("push protection", "secret_scanning_push_protection")):
        status = (sec.get(key) or {}).get("status")
        if status == "enabled":
            out.append(Result("PASS", label, "enabled"))
        elif status is None:
            out.append(Result("SKIP", label, "GitHub did not report it (you may lack admin access)"))
        else:
            out.append(Result(severity(public), label, "off", "Settings > Code security"))
    return out


def check_vulnerability_reporting(api, repo: str, public: bool) -> Result:
    data = api.get(f"repos/{repo}/private-vulnerability-reporting")
    if not isinstance(data, dict):
        return Result("SKIP", "private vulnerability reporting", "GitHub did not report it")
    if data.get("enabled"):
        return Result("PASS", "private vulnerability reporting", "enabled")
    return Result(severity(public), "private vulnerability reporting", "off", "Settings > Code security")


def default_branch_rules(api, repo: str, branch: str) -> tuple:
    """(blocks force push, blocks deletion, required check names) from active rulesets and classic protection."""
    force = delete = False
    required: set = set()
    listing = api.get(f"repos/{repo}/rulesets")
    for entry in listing if isinstance(listing, list) else []:
        ruleset = api.get(f"repos/{repo}/rulesets/{entry.get('id')}")
        if not isinstance(ruleset, dict) or ruleset.get("enforcement") != "active" or ruleset.get("target", "branch") != "branch":
            continue
        refs = ((ruleset.get("conditions") or {}).get("ref_name") or {}).get("include") or []
        if not any(r in ("~DEFAULT_BRANCH", "~ALL", f"refs/heads/{branch}") for r in refs):
            continue
        for rule in ruleset.get("rules") or []:
            if rule.get("type") == "non_fast_forward":
                force = True
            elif rule.get("type") == "deletion":
                delete = True
            elif rule.get("type") == "required_status_checks":
                for check in (rule.get("parameters") or {}).get("required_status_checks") or []:
                    required.add(check.get("context", ""))
    classic = api.get(f"repos/{repo}/branches/{branch}/protection")
    if isinstance(classic, dict):
        force = force or not (classic.get("allow_force_pushes") or {}).get("enabled", True)
        delete = delete or not (classic.get("allow_deletions") or {}).get("enabled", True)
        required.update((classic.get("required_status_checks") or {}).get("contexts") or [])
    return force, delete, required


def check_branch_rules(force: bool, delete: bool, public: bool) -> Result:
    name = "default branch rules"
    if force and delete:
        return Result("PASS", name, "force pushes and deletion are blocked")
    missing = " and ".join(x for x, ok in (("force pushes", force), ("deletion", delete)) if not ok)
    return Result(severity(public), name, f"{missing} not blocked", "Settings > Rules > Rulesets")


def skippable_workflows(clone: Path) -> dict:
    """Workflow job ids and names mapped to True when the workflow has a path filter on its trigger."""
    found: dict = {}
    for path in sorted((clone / ".github" / "workflows").glob("*.y*ml")):
        text = path.read_text(errors="replace")
        head, _, jobs = text.partition("\njobs:")
        filtered = bool(re.search(r"^\s+paths(-ignore)?:", head, re.MULTILINE))
        for match in re.finditer(r"^  ([A-Za-z0-9_-]+):\s*$", jobs, re.MULTILINE):
            found[match.group(1)] = filtered
        for match in re.finditer(r"^    name:\s*(.+?)\s*$", jobs, re.MULTILINE):
            found[match.group(1).strip("\"'")] = filtered
    return found


def check_required_checks(clone: Path, required: set) -> Result:
    name = "required checks can run on every pull request"
    if not required:
        return Result("PASS", name, "no required checks")
    jobs = skippable_workflows(clone)
    bad = sorted(c for c in required if jobs.get(c))
    if bad:
        return Result("FAIL", name, f"{len(bad)} required check(s) sit in a workflow with a path filter: a pull request "
                      "that skips it waits forever", "remove the paths filter, or stop requiring that check")
    unknown = sorted(c for c in required if c not in jobs)
    if unknown:
        return Result("WARN", name, f"{len(unknown)} required check(s) match no job in this clone's workflows")
    return Result("PASS", name, f"{len(required)} required check(s), none behind a path filter")


def check_community(clone: Path) -> Result:
    missing = [label for label, options in COMMUNITY if not any((clone / o).exists() for o in options)]
    if missing:
        return Result("WARN", "community files", "missing: " + ", ".join(missing))
    return Result("PASS", "community files", "all present")


def check_artifacts(api, repo: str) -> Result:
    data = api.get(f"repos/{repo}/actions/artifacts")
    if not isinstance(data, dict):
        return Result("SKIP", "CI artifacts", "GitHub did not report them")
    total = data.get("total_count", 0)
    if total:
        return Result("WARN", "CI artifacts", f"{total} stored; artifacts and run logs are public when the repository is",
                      "open one, then delete what should not be public")
    return Result("PASS", "CI artifacts", "none stored (run logs are still public: read one)")


def check_signed_out(repo: str, public: bool, fetch: Callable[[str], int]) -> Result:
    status = fetch(f"https://api.github.com/repos/{repo}")
    if public:
        ok, want = status == 200, "visible"
    else:
        ok, want = status == 404, "hidden"
    if status == 0:
        return Result("SKIP", "signed-out view", "no network answer")
    return Result("PASS" if ok else "FAIL", "signed-out view", f"expected {want} when signed out, got HTTP {status}")


def run_checks(clone: Path, repo: str, api, fetch: Callable[[str], int] = signed_out_status,
               report_dir: Path = REPORT_DIR) -> list:
    info = api.get(f"repos/{repo}")
    if not isinstance(info, dict):
        raise RuntimeError(f"GitHub did not return {repo}. Is gh signed in, and is the name right?")
    public = info.get("visibility") == "public" or info.get("private") is False
    branch = info.get("default_branch", "main")
    force, delete, required = default_branch_rules(api, repo, branch)
    results = [Result("PASS", "visibility", "public" if public else "private (not flipped yet)"),
               check_history_audit(clone, report_dir)]
    results += check_scanning(info, public)
    results += [check_vulnerability_reporting(api, repo, public),
                check_branch_rules(force, delete, public),
                check_required_checks(clone, required),
                check_community(clone),
                check_artifacts(api, repo),
                check_signed_out(repo, public, fetch)]
    return results


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Check a repository against the pre-public checklist (read-only).")
    ap.add_argument("clone", help="path to a local clone")
    ap.add_argument("--repo", help="owner/name, when origin is not a GitHub remote")
    args = ap.parse_args(argv)
    clone = Path(args.clone)
    repo = args.repo or repo_from_remote(clone)
    if not (clone / ".git").exists() or not repo:
        print("prepublic_check: give a local clone with a GitHub origin, or pass --repo owner/name.", file=sys.stderr)
        return 2
    try:
        results = run_checks(clone, repo, GhApi())
    except RuntimeError as err:
        print(f"prepublic_check: {err}", file=sys.stderr)
        return 2
    print(f"prepublic_check: {repo}")
    for r in results:
        print(f"{r.status:<5} {r.name}: {r.detail}" + (f"  [{r.fix}]" if r.fix and r.status != "PASS" else ""))
    counts = {s: sum(1 for r in results if r.status == s) for s in ("PASS", "WARN", "FAIL", "SKIP")}
    print(f"{counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail, {counts['SKIP']} skipped")
    print("Not checked here: read one CI run log, and look at the repository signed out in a private window.")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
