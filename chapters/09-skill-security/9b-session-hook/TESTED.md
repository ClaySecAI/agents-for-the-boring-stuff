# Chapter 9B: what we tested

Back to the [chapter](README.md).

**Tested**

- `test_skillgate.py` covers the hook's output and logic: the counts it reports, the warning for an item that is not vetted,
  no warning once an item is adopted, the CHANGED status after an edit, the MISSING status after a delete, and that it never
  exits with an error. It also covers a skill installed as a link (named in the line, CHANGED when the folder it points to
  changes or the link is moved), a folder named `synced` (audited unless it has the app's layout), `forget` (refusing without
  `--yes`, refusing an item still on disk, then clearing MISSING), `adopt` (refusing without `--yes`, refusing a high finding,
  accepting a risk), and `audit`. All pass on Python 3.9 and 3.15.
- On this repository the hook ran from the command line and reported six items as not vetted before we adopted them.

Seen once in practice: a new session started in a separate worktree reported that two items we had edited after adopting them
(the `editor` agent and the `edit-chapter` skill) had changed since release. We saw that second-hand, in the session's report,
and not on our own screen.

**Not tested**

- How the line looks in the CLI as opposed to the app.
- The hook firing in a fresh session on our own screen. We have the second-hand report above, once.
- The app's synced bundle in any layout other than the one on our machine. The code treats a layout it does not recognize as an
  ordinary folder, so we expect a changed layout to show as not vetted: noisy, not silent.
- Any system other than a Mac.

**How much to trust it**

The unit tests show the hook counts and reports what is on disk correctly, but we have watched it fire in a real session only
second-hand, so check that your first session prints a `skillgate:` line before you rely on it.
