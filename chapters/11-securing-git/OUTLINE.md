# Chapter 11 outline: Securing git before you publish

An outline for a chapter, not yet prose. It records what the chapter will teach, what was built and tested
while preparing this book's own repositories for publication, and the decisions still open.

## What the chapter is for

Agents commit for you. They are fast, they do not get tired, and they will commit a home-directory path, a
real name, or a token as readily as anything else. This chapter sets up the checks that stop that before it
reaches GitHub, on every repository on the machine, and shows how to find and fix what already got through.
Its reader is about to make a repository public, or has just done so.

The chapter follows the book's method. Rules supply guarantees, a person decides, and every check is tested by
planting a fake leak and watching it get caught.

## Planned sections

### 11.1 What leaks, and where it hides

- Secrets (keys, tokens) and personal data (names, emails, addresses, account numbers, file names) are
  different problems with different tools.
- Places people forget: commit author and committer fields, file names, old commits, tags, CI logs, CI
  artifacts, and issue and pull request text.
- History is permanent in practice. Deleting a file in a new commit leaves it in every earlier one.

### 11.2 Your commit identity

- Use GitHub's noreply address as `user.email`, globally.
- A repository can override it locally, and one of ours did, with a personal address. Another had a personal
  address on commits from years before the switch.
- How to check: list the distinct author and committer emails in a repository's history.

### 11.3 The repository's own guard

- `.gitignore` is a request; `git add -f` overrides it.
- The book's guard, `scripts/check_repo_clean.py`: an allowlist of file types, fixed patterns, a size limit, and
  a private blocklist kept inside `.git`, so it is never committed.
- It prints where a match is, never what matched. Terminal output ends up in scrollback, logs, and bug reports.
- A bug worth teaching: the guard looked for the blocklist with `git rev-parse --git-dir`, which in a linked
  worktree points somewhere else, so the blocklist silently did not run. The fix is `--git-common-dir`, with a
  test that fails on the old line.

### 11.4 One set of hooks for every repository

- `core.hooksPath` set globally sends every repository's hooks to one folder.
- A dispatcher runs, in order: gitleaks on the staged changes, a personal-data check, then the repository's own
  hook. Without that last step, a global hooks path switches every repository's own hooks off.
- The personal-data check: a whole-word blocklist outside every repository, the home path, and a refusal when
  the commit email is not a noreply address.
- Whole words matter. A short name on the blocklist matched "cron", "front", and "environment" until matching
  required word boundaries. A brand name on the list blocks ordinary commits; that one is a deliberate
  `--no-verify`.
- A repository meant to hold personal data opts in, in its own `.git/config`, and may then push only to a
  repository GitHub confirms is private. Secret scanning still runs there.
- The hook caught its own author: an example word in a code comment was a name on the blocklist.

### 11.5 Checking what is already there

- Scan full history with gitleaks, with redaction on.
- Scan history, file names and commit metadata against the blocklist, printing counts only.
- A clean result means nothing until a control passes: plant a fake token, commit it, delete it in a second
  commit, and confirm the history scan still finds it.
- Read every hit in context. Most of ours were public records, documentation of the patterns themselves, or a
  name the author put on a profile page on purpose.

### 11.6 Fixing history, and what it cannot fix

- Rewriting author emails across a repository, keeping tags in step, and checking that the file tree is
  byte-for-byte unchanged.
- `--force-with-lease`, so the rewrite is refused if anyone pushed in the meantime.
- What a rewrite does not reach: existing clones, forks, caches, and GitHub's hidden references to pull request
  commits. Only GitHub Support can purge those.

### 11.7 Before you flip a repository public

A checklist, in the order it was done for this book:

- Scan history (11.5) and fix it (11.6) while the repository is still private.
- CI that runs the repository's guard and a gitleaks history scan on every push and pull request.
- Make it public, then at once turn on what GitHub offers only for public repositories on a free plan: secret
  scanning with push protection, private vulnerability reporting, and branch rules.
- Branch rules that fit the repository: block force pushes and deletion everywhere; require checks only if
  every pull request can produce them. A required check that a workflow skips for documentation changes
  blocks those pull requests forever.
- Check what CI publishes: run logs and artifacts are public too.
- Community files: a security policy, contributing guide, code of conduct, and issue and pull request templates
  that ask people not to paste their own file names, hostnames, or tokens.
- Look at the result signed out.

### 11.8 Where agents fit

- Agent commits go through the same hooks, which is the point of making them global.
- Chapter 9's skill gate covers what agents are told, not what they commit.
- Chapter 8's design note adds a local model that reads diffs for what the rules miss.

### Limits, Common tasks, Exercises

- Limits: rules find what someone wrote down; history fixes do not reach copies; the blocklist itself is
  personal data and has no backup by design; push protection knows only known secret formats.
- Common tasks: install the hooks, add a term, opt a private repository in, scan a repository, check a
  repository before publishing.
- Exercises on a practice repository with invented names and a fake token, never real data.

## What was built and tested while preparing this repository

These become TESTED.md once the chapter is written. Single runs on one Mac.

- The global hook blocked a fake GitHub token, a real-looking email as commit author or committer, the home path,
  a blocklist term in a line and in a file name, and let clean commits through. Eight cases, then five more after the
  switch to whole-word matching.
- File names in the hook's output are masked, so a blocked file name does not print the matched term.
- The opt-in for private repositories: pushes to a private GitHub repository passed; pushes to a public one, a
  missing one, and a non-GitHub host were refused. 10 cases, run without pushing anything.
- A full-history gitleaks scan of seven repositories found nothing, and the control test found the planted token.
- The worktree bug in the repository guard, with a test that fails on the old code and passes on the fix.
- A history rewrite of one public repository: 18 commits moved to a noreply address, tree unchanged, tag moved,
  force push guarded by a lease.
- Not tested: the force-push rule against an actual force push; a second machine; Linux; Windows.

## Decisions still open

- The chapter number. It reads best before Chapter 8, which builds on these hooks.
- Where the hook code lives in public. Today the dispatcher and the personal-data check live in the author's
  private setup repository. The chapter needs them here, in its own folder, the way Chapter 9 ships
  `skillgate.py`; the private setup would then copy them from the book.
- How much of the publishing checklist (11.7) belongs here and how much in a short appendix.
