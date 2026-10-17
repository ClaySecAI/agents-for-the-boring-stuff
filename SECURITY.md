# Security

The scripts in this repository read, classify and move your files, and some of those files hold the
most sensitive things you own. Please report anything that could cause harm.

## Reporting a problem

Use GitHub's private reporting: open the **Security** tab of this repository and choose **Report a
vulnerability**. Only the maintainer can see the report. Do not open a public issue for a security
problem, and do not paste real file names, file contents, logs or plans into any report. Describe
the problem with the fixture (`make_mess.py`, `make_project_mess.py`) or with made-up names.

You should get a first answer within a week. This is a one-person project, so a fix may take longer.

## What counts

- A file moved, renamed, overwritten or deleted in a way the approved plan did not say, or that
  `undo_plan.py` cannot reverse.
- File names or contents leaving your machine when the text says they stay local, for example on
  the local-model or Apple Foundation Models paths.
- Text inside a file that steers a model into a different plan (prompt injection) and gets past the
  validator.
- A way to commit personal data that `scripts/check_repo_clean.py` should catch and does not.
- A plan, manifest, log or snapshot written somewhere the documentation does not mention, such as
  a synced folder.

Wrong labels and poor sorting are bugs, not security problems. Open a normal issue for those.

## Before you run anything on real files

This is teaching code, provided as is and without warranty (see [LICENSE](LICENSE)). Practice on the
fixture first. Back up a folder before the first real run, read every plan before you approve it, and
start an unattended sweep only after several supervised runs have gone the way you expected.
