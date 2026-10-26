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
- `example_personal_data_check.py`: 10 tests on scratch repositories with a scratch home folder and an invented blocklist term. They
  cover a clean change, a term found and never printed, whole-word matching, case, only added lines counting, a home path found and
  not printed, a non-noreply email refused and not printed, `hooks.allowEmail`, a missing blocklist, and running outside a repository.
- `retention_check.py`: 10 tests against a fake GitHub, with no network. They cover a report that changes nothing, `--apply` setting
  only the repositories that differ and reading each back, a setting that does not stick, one that cannot be read, archived
  repositories, a custom target, days outside 1 to 90, and a failed repository listing.
- The retention check on the author's account: it found one new repository at 90 days, `--apply` set it to 7 and read it back, and
  a second run showed all 33 repositories at 7 days. The author deleted older artifacts and runs with separate `gh api` commands;
  the script does not do that and no test covers it.
- `push-verifier` three times on this repository before a push. The first run said NOT PUSHABLE because the history audit report was
  older than the last commit, and it also showed that its own guard command needed a flag. After we fixed both, the later runs said
  PUSHABLE WITH WARNINGS with no blockers.
- All five test suites in this chapter on Python 3.9 and 3.12 in CI, on macOS: all passed.
- `audit_history.py` on one Ubuntu 24.04 machine (Python 3.12): with Ubuntu's apt gitleaks 8.16 the control failed, because that
  build has no `gitleaks git` subcommand, and the message said only that the planted token was not found. With a gitleaks 8.30.1
  release binary the control passed and the audit ran on 16 private repositories, the largest with 682 commits. The version check
  that now names the cause came from that run. Its three tests, with a stub gitleaks on PATH standing in for an old, a
  current, and a missing build, and the matching `drift_check.py` test, pass on that machine.

## Not tested

- The author's own hook scripts in 8.4. The author ran them on one Mac while preparing this book's repositories, but they are in a
  private repository, so those runs cannot be repeated from here. The example script is tested, but it is a separate, shorter program.
- A history rewrite. 8.6 describes how to check one; nothing in this chapter's tests rewrites history.
- The force-push rule against an actual force push.
- LM Studio as the model server, and any model other than `ministral-3:8b`.
- How accurate the model's verdicts are. We looked at a handful, not a measured set.
- `audit_history.py` on a large repository. The largest we ran had 101 commits.
- `prepublic_check.py` against a repository that is actually misconfigured. The failing cases run against a fake GitHub.
- The signed-out check against a private repository on the real service.
- `retention_check.py` setting a repository it cannot change, such as one where you lack admin rights, and an archived repository on
  the real service. Those cases run against a fake GitHub.
- `push-verifier` on a repository with a real problem. We did not plant a fake leak in a commit and check that its diff read and its
  verdict catch it, and we did not measure how often its reading of a diff misses something.
- A second Mac, and Windows. On Linux, only `audit_history.py` has run (above); `drift_check.py` and the other scripts have not.

## How much to trust it

The tests show each check finds what it was built to find and that the model cannot shorten the list, but the real runs are single
runs on one Mac and the failing cases ran on invented data, so treat a clean result as "nothing we know to look for", not as proof.
