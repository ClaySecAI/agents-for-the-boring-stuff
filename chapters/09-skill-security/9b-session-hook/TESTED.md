# Chapter 9B: what we tested

Back to the [chapter](README.md).

`test_skillgate.py` covers the hook's output and logic: the counts it reports, the warning for an item that is not vetted, no
warning once an item is adopted, the CHANGED status after an edit, and that it never exits with an error. It also covers `adopt`
(refusing without `--yes`, refusing a high finding, accepting a risk) and `audit`. On this repository the hook ran from the command
line and reported six items as not vetted before we adopted them.

Not tested: the MISSING status; the hook firing automatically at the start of a real Claude Code session (we ran the command, and
wired it into `settings.json`, but did not watch a fresh session print the line); and how the line looks in the CLI as opposed to the
app.
