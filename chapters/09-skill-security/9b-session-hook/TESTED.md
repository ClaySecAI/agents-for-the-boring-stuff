# Chapter 9B: what we tested

Back to the [chapter](README.md).

`test_skillgate.py` covers the hook's output and logic: the counts it reports, the warning for an item that is not vetted, no
warning once an item is adopted, the CHANGED status after an edit, and that it never exits with an error. It also covers `adopt`
(refusing without `--yes`, refusing a high finding, accepting a risk) and `audit`. On this repository the hook ran from the command
line and reported six items as not vetted before we adopted them.

Seen once in practice: a new session started in a separate worktree reported that two items we had edited after adopting them
(the `editor` agent and the `edit-chapter` skill) had changed since release. We saw that second-hand, in the session's report, and not on
our own screen.

Not tested: the MISSING status, and how the line looks in the CLI as opposed to the app.
