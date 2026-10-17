# Contributing

Corrections, bug reports and pull requests are welcome. The project tests its code on real folders,
so the one rule that matters most is about what never goes into git.

## Never commit real data

That means no real files, and nothing derived from them: plans, manifests, labels, project lists,
snapshots, reports, model logs, screenshots or pasted output. A file name alone can say a lot ("2025
W2.pdf", a doctor's name, a client). Once pushed to a public repository, data may be copied and
indexed, and deleting the commit does not undo that.

- Test against the fixtures (`make_mess.py`, `make_project_mess.py`). If a bug needs a new case,
  add a made-up file to a fixture and leave your real one out.
- In issues and pull requests, rename the details: "a PDF from my bank", not the file name.
- Keep experiments in a `practice*` folder. Git ignores it and the guard refuses it.

## Set up the guard

Turn on the pre-commit hook once per clone, and add your own private terms:

```bash
git config core.hooksPath .githooks
echo "your-username" >> .git/private-terms.txt
python3 scripts/test_check_repo_clean.py
```

The blocklist lives inside `.git/`, so it is never committed. Put your name, username, the name of
your computer, your employer and any real file names you tested with in it.

The same guard runs on GitHub for every pull request, together with a secret scan of the history
(see [.github/workflows/checks.yml](.github/workflows/checks.yml)). That copy cannot see your private
blocklist, so the hook on your machine is still the layer that knows your names.

## If the guard blocks you

It prints the file and line, never the matched text. Fix the line or unstage the file. If the guard
is wrong, for example about an address on a domain made for documentation, say so in the pull
request and change the guard and its tests in the same commit. Do not get past it with
`--no-verify`.

## Code and tests

- Match the style of the file you are changing. Scripts use the standard library only, unless a
  chapter says otherwise, and must run on Python 3.9 (start each file with
  `from __future__ import annotations`). CI tests 3.9 and 3.12.
- Run the tests for the chapter you touched before you open a pull request:

  ```bash
  python3 chapters/01-files-and-folders/test_roundtrip.py
  python3 chapters/01-files-and-folders/1d-projects/test_projects.py
  python3 chapters/01-files-and-folders/1d-projects/test_sweep.py
  ```

- Anything that moves files needs a plan you can read, a manifest and a working undo, with a test that
  shows all three.

## Security problems

Report them privately. See [SECURITY.md](SECURITY.md).
