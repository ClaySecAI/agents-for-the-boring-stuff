# Agents for the Boring Stuff

Automating tedious computer work, with agents instead of scripts.

Many people learned Python from *Automate the Boring Stuff with Python*: you
write code, and the code does the chore. This project asks a different
question: **what if you describe the chore, and an agent does it?**

You still learn real skills. They're just different ones:

1. **Specify the task.** State a clear goal, constraints, and a definition of done.
2. **Scope the agent.** Decide which tools and folders it can touch, and what needs your approval.
3. **Verify the result.** Never trust "done" without a check.
4. **Make it repeatable.** Package it as a skill, then schedule it.

> This is an independent project, not affiliated with or endorsed by the
> book or its author. It follows the book's *topics* as an inspiration. No
> book text or code is reproduced here. If you want to learn to write the
> code yourself, buy or read the book. It's excellent.

## How each chapter works

Every chapter folder follows the same shape:

| Piece | What it is |
|---|---|
| `README.md` | The lesson: the chore, the setup, what to try, where it breaks |
| An **agent file** (`.claude/agents/`) | A specialist with a narrow job and limited tools |
| A **skill** (`.claude/skills/`) | A repeatable procedure the agent follows |
| A **fixture** | Safe, fake data to practice on (never your real files first) |
| A **verifier** | A small check that proves the agent did what it claimed |

The pattern repeated in every chapter is **propose, approve, apply, verify**.
The agent writes a plan first. You read it. Only then does it act, and
a script checks the outcome.

## Chapters

| # | Topic | Status |
|---|---|---|
| 01 | [Files and folders](chapters/01-files-and-folders/) | Ready |
| 01B | [Files, privately: local model (LM Studio / Ollama)](chapters/01-files-and-folders/1b-local-model/) | Ready |
| 01C | [Files, privately: Apple on-device model](chapters/01-files-and-folders/1c-apple-foundation-models/) | Ready |
| 02 | Messy text and documents | Planned |
| 03 | Spreadsheets, PDFs, Word files | Planned |
| 04 | Email triage (draft, never auto-send) | Planned |
| 05 | Web checking with a browser agent | Planned |
| 06 | GUI automation with computer use | Planned |
| 07 | Scheduling it all | Planned |

## Keeping personal data out of this repo

These chapters get tested on real-looking files, and sometimes real ones. Nothing real
belongs in git, so there are two layers:

1. **`.gitignore`** skips practice folders, labels, plans, snapshots and compiled helpers. It is
   only a request: `git add -f` overrides it.
2. **A pre-commit guard** ([`scripts/check_repo_clean.py`](scripts/check_repo_clean.py)) inspects what is
   actually about to be committed and refuses the commit if a file isn't on a short allowlist
   (docs, source, one settings file), is large, or contains a home path, email address,
   SSN-shaped number, key, or any term from your private blocklist. It never prints what it
   matched, only where.

Turn it on once per clone, and keep your own blocklist inside `.git/` where it is never committed:

```bash
git config core.hooksPath .githooks
echo "your-username" >> .git/private-terms.txt     # names, employer, real filenames you tested with
python3 scripts/test_check_repo_clean.py           # the guard has its own tests
```

Use practice folders for real-file experiments, delete them when you're done, and remember
that logs can hold copies too (see [1B](chapters/01-files-and-folders/1b-local-model/README.md)).

## Getting started

You need [Claude Code](https://claude.com/claude-code) and Python 3.9+
(only for the fixture and verifier scripts, since the agent does the actual work).

```bash
git clone <this repo>
cd agents-for-the-boring-stuff
claude
```

Then open [Chapter 1](chapters/01-files-and-folders/README.md).

## License

MIT. See [LICENSE](LICENSE).
