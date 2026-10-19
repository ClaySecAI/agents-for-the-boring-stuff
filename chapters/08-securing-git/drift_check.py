#!/usr/bin/env python3
"""Check that every repository on this machine still gets the global git protections. Read-only.

    python3 drift_check.py [folder ...] [--depth N]       # default folder: ~/Developer

The global hooks protect nothing in a repository that quietly steps around them. This walks the folders you
name, finds every repository, and reports drift:

  machine:  the global hooks folder is set and complete, gitleaks is installed, the global commit email is a
            GitHub noreply address, the blocklist exists and is private to you.
  per repo: a local user.email that is not a noreply address, a local core.hooksPath that replaces the global
            hooks, a repository that allows personal data but has a remote that is not a private GitHub
            repository, and a remote URL with a password or token inside it.

It never prints a term from your blocklist, an email address, or a token. Exit codes: 0 no FAIL, 1 at least one
FAIL, 2 it could not run.
"""
from __future__ import annotations

import argparse
import dataclasses
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

NOREPLY = "@users.noreply.github.com"
PROTECTED_HOOKS = ("pre-commit", "pre-push")
SKIP_DIRS = {"node_modules", ".venv", "venv", "__pycache__", ".git"}


@dataclasses.dataclass
class Finding:
    status: str    # PASS, WARN, FAIL
    where: str     # "machine" or a repository name
    detail: str
    fix: str = ""


def git_config(repo: Optional[Path], *args: str) -> str:
    cmd = ["git", "-C", str(repo)] if repo else ["git"]
    return subprocess.run([*cmd, "config", *args], capture_output=True, text=True).stdout.strip()


def github_repo(url: str) -> Optional[str]:
    match = re.match(r"(?:https://(?:[^@/]+@)?github\.com/|git@github\.com:|ssh://git@github\.com/)"
                     r"([^/]+/[^/]+?)(?:\.git)?/?$", url)
    return match.group(1) if match else None


def gh_visibility(repo: str) -> str:
    try:
        done = subprocess.run(["gh", "repo", "view", repo, "--json", "visibility", "-q", ".visibility"],
                              capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


# --- the machine -------------------------------------------------------------------------------------

def check_machine(terms_file: Path) -> list:
    out = []
    hooks = git_config(None, "--global", "--get", "core.hooksPath")
    folder = Path(hooks).expanduser() if hooks else None
    if not folder or not folder.is_dir():
        out.append(Finding("FAIL", "machine", "the global core.hooksPath is not set to a folder that exists",
                           "run the hook installer"))
    else:
        dispatch = folder / "dispatch"
        if not dispatch.is_file() or not dispatch.stat().st_mode & 0o111:
            out.append(Finding("FAIL", "machine", "the global hooks folder has no executable dispatch script", "rerun the installer"))
        for name in PROTECTED_HOOKS:
            hook = folder / name
            if not hook.exists() or hook.resolve() != dispatch.resolve():
                out.append(Finding("FAIL", "machine", f"the global {name} hook is not the dispatch script", "rerun the installer"))
        if not any(f.where == "machine" for f in out):
            out.append(Finding("PASS", "machine", "global hooks folder is set and complete"))
    if shutil.which("gitleaks"):
        out.append(Finding("PASS", "machine", "gitleaks is installed"))
    else:
        out.append(Finding("FAIL", "machine", "gitleaks is not installed, so every commit is refused", "brew install gitleaks"))
    email = git_config(None, "--global", "--get", "user.email").lower()
    out.append(Finding("PASS" if email.endswith(NOREPLY) else "FAIL", "machine",
                       "global commit email is a GitHub noreply address" if email.endswith(NOREPLY)
                       else "global commit email is not a GitHub noreply address",
                       "" if email.endswith(NOREPLY) else "git config --global user.email <id>+<username>" + NOREPLY))
    if not terms_file.is_file():
        out.append(Finding("FAIL", "machine", "no private blocklist file", "the installer creates an empty one; add your terms"))
    else:
        terms = [t for t in terms_file.read_text().splitlines() if t.strip() and not t.startswith("#")]
        out.append(Finding("PASS" if terms else "WARN", "machine", f"private blocklist has {len(terms)} term(s)",
                           "" if terms else "an empty blocklist checks emails and the home path only"))
        if terms_file.stat().st_mode & 0o077:
            out.append(Finding("FAIL", "machine", "the private blocklist can be read by other users", f"chmod 600 {terms_file}"))
    return out


# --- repositories ------------------------------------------------------------------------------------

def find_repos(roots: list, depth: int) -> list:
    found: list = []

    def walk(folder: Path, level: int) -> None:
        if (folder / ".git").exists():
            found.append(folder)
            return
        if level >= depth:
            return
        try:
            children = sorted(p for p in folder.iterdir() if p.is_dir() and p.name not in SKIP_DIRS and not p.is_symlink())
        except OSError:
            return
        for child in children:
            walk(child, level + 1)

    for root in roots:
        walk(root, 0)
    return found


def check_repo(repo: Path, global_hooks: str, visibility: Callable[[str], str]) -> list:
    name, out = repo.name, []
    local_email = git_config(repo, "--local", "--get", "user.email").lower()
    allowed = git_config(repo, "--get-all", "hooks.allowEmail").lower().split()
    if local_email and not local_email.endswith(NOREPLY) and local_email not in allowed:
        out.append(Finding("FAIL", name, "a local user.email overrides the global one and is not a noreply address",
                           "git config --local --unset user.email"))
    local_hooks = git_config(repo, "--local", "--get", "core.hooksPath")
    if local_hooks and Path(local_hooks).expanduser() != Path(global_hooks).expanduser():
        out.append(Finding("FAIL", name, "a local core.hooksPath replaces the global hooks",
                           "unset it, and use git config hooks.chainPath for the repository's own hooks"))
    remotes = [l.split()[1] for l in subprocess.run(["git", "-C", str(repo), "remote", "-v"], capture_output=True,
                                                    text=True).stdout.splitlines() if "(push)" in l]
    for url in remotes:
        if re.match(r"https?://[^/@\s]+:[^/@\s]+@", url) or re.match(r"https?://[^/@\s]{20,}@", url):
            out.append(Finding("FAIL", name, "a remote URL has a password or token inside it",
                               "git remote set-url origin <the URL without credentials>, then revoke that token"))
    if git_config(repo, "--type=bool", "--get", "hooks.allowPersonalData") == "true":
        if not remotes:
            out.append(Finding("PASS", name, "allows personal data and has no remote"))
        for url in remotes:
            slug = github_repo(url)
            seen = visibility(slug) if slug else ""
            if seen != "PRIVATE":
                why = "is not on GitHub" if not slug else (f"is {seen.lower()}" if seen else "could not be confirmed private")
                out.append(Finding("FAIL", name, f"allows personal data, and a remote {why}",
                                   "remove the remote, or unset hooks.allowPersonalData"))
    if not out:
        out.append(Finding("PASS", name, "no drift"))
    return out


def run(roots: list, depth: int, terms_file: Path, visibility: Callable[[str], str] = gh_visibility) -> list:
    results = check_machine(terms_file)
    global_hooks = git_config(None, "--global", "--get", "core.hooksPath")
    for repo in find_repos(roots, depth):
        results += check_repo(repo, global_hooks, visibility)
    return results


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(description="Report repositories that step around the global git protections.")
    ap.add_argument("folders", nargs="*", default=[str(Path.home() / "Developer")])
    ap.add_argument("--depth", type=int, default=3, help="how many folders down to look (default 3)")
    ap.add_argument("--terms", default=str(Path.home() / ".config" / "git" / "private-terms.txt"))
    args = ap.parse_args(argv)
    roots = [Path(f).expanduser() for f in args.folders]
    missing = [r for r in roots if not r.is_dir()]
    if missing:
        print(f"drift_check: {len(missing)} folder(s) do not exist.", file=sys.stderr)
        return 2
    results = run(roots, args.depth, Path(args.terms))
    for f in results:
        if f.status != "PASS":
            print(f"{f.status:<5} {f.where}: {f.detail}" + (f"  [{f.fix}]" if f.fix else ""))
    repos = sorted({f.where for f in results if f.where != "machine"})
    bad = sorted({f.where for f in results if f.status == "FAIL"})
    print(f"{len(repos)} repositor{'y' if len(repos) == 1 else 'ies'} checked, "
          f"{sum(1 for f in results if f.status == 'FAIL')} fail, {sum(1 for f in results if f.status == 'WARN')} warn"
          + (f" ({', '.join(bad)})" if bad else ""))
    return 1 if any(f.status == "FAIL" for f in results) else 0


if __name__ == "__main__":
    sys.exit(main())
