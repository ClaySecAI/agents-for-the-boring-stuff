# Chapter 8: what we tested

Back to the [chapter](README.md).

## Tested

- `audit_history.py`: 21 tests on invented repositories, run on one Mac. They plant a token and delete it in a second commit, a
  blocklist term in a line, a file name and a commit message, a home path, and a non-noreply email, and check each is found and
  that the matched text is in neither the output nor the saved report. They also cover a model stub that approves everything (the
  hit stays and the exit code is still 1), a stub that returns text or values outside the lists (the hit becomes `unsure`), a
  model that is down, a remote model URL (refused before any scan), the `--max-triage` limit, and the report file mode (0600).
- The same script on three real repositories of the author, with the real blocklist and `ministral-3:8b` through Ollama: two had no
  hits, and one had a single hit that the model called `public_or_deliberate` with high confidence. The author's profile page
  carries a name on purpose.
- The model call on this book's repository with a stand-in term list: 341 hits, and the model sorted the first 8 in about 8
  seconds. We did not measure how often its verdicts are right.
- `prepublic_check.py`: 16 tests against a fake GitHub, with no network. They cover a public repository without protection, a
  private one (warnings, not failures), force pushes or deletion blocked in a ruleset or by classic protection, a ruleset that is
  off or aimed at another branch, a required check behind a path filter, missing community files, stored artifacts, an audit
  report that is missing, has hits, or is older than the last commit, and settings GitHub did not report (SKIP, not PASS).
- The same script on this repository: 9 passes and 1 warning, for 20 stored continuous integration (CI) artifacts. We downloaded one: a gitleaks result
  file with no findings.
- `drift_check.py`: 16 tests on scratch repositories with a scratch global git configuration. They cover a missing or incomplete
  hooks folder, a non-noreply global email, a blocklist that is empty or readable by others, a local email override, a local
  `core.hooksPath`, a credential in a remote URL, personal-data repositories with private, public, unknown, and non-GitHub remotes,
  and the depth limit.
- The same script on the author's machine: three repositories, no drift.

## Not tested

- The hook scripts in 8.4. The author ran them on one Mac while preparing this book's repositories, but the scripts are not in this
  repository yet, so those runs cannot be repeated from here.
- A history rewrite. 8.6 describes how to check one; nothing in this chapter's tests rewrites history.
- The force-push rule against an actual force push.
- LM Studio as the model server, and any model other than `ministral-3:8b`.
- How accurate the model's verdicts are. We looked at a handful, not a measured set.
- `audit_history.py` on a large repository. The largest we ran had 98 commits.
- `prepublic_check.py` against a repository that is actually misconfigured. The failing cases run against a fake GitHub.
- The signed-out check against a private repository on the real service.
- Python 3.9. We checked that the syntax parses as 3.9; the test suites ran on the Python 3 that is on the author's Mac. The
  continuous-integration workflow runs them on 3.9 and 3.12.
- A second machine, Linux, and Windows.

## How much to trust it

The tests show each check finds what it was built to find and that the model cannot shorten the list, but the real runs are single
runs on one Mac and the failing cases ran on invented data, so treat a clean result as "nothing we know to look for", not as proof.
