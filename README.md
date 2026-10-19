# Agents for the Boring Stuff

Automating tedious computer work with agents instead of scripts.

A classic way to learn programming is to automate chores in Python: you write code, and the
code does the work. This project starts from the other end. You describe the chore, and an
agent does it.

You still learn skills, but they are different ones:

1. Specifying the task: a clear goal, constraints, and a definition of done.
2. Scoping the agent: which tools and folders it may touch, and what needs your approval.
3. Verifying the result: never accepting "done" without an independent check.
4. Making the work repeatable: packaging it as a skill, then scheduling it.

## Who this is for

You are comfortable in a terminal and have written some Python or shell. You do not need to
know how agents work. You do need [Claude Code](https://claude.com/claude-code) and Python 3.9
or later. The scripts use only the standard library, and the agent does the actual work.

## How each chapter is built

A full chapter, such as 1, 1D, or 10, uses the parts below. Concept chapters and notes do not. Agent
files and skills are not in the chapter folder: they live in `.claude/`, where Claude Code finds them.

| Part | Contents |
|---|---|
| `README.md` | The lesson: the task, the setup, the checks, the limits, and some exercises |
| An agent file (`.claude/agents/`) | A specialist with a narrow job and a limited set of tools |
| A skill (`.claude/skills/`) | A repeatable procedure the agent follows |
| A fixture | Fake data to practice on, so that your real files come later and only with care |
| A verifier | A script that checks what the agent claims to have done |

Each chapter follows one pattern: propose, approve, apply, verify. The agent writes a plan.
You read it. Only then does anything change, and a script checks the result.

Behind that pattern is a division of labor that returns in every chapter:

- You supply intent and vocabulary: what counts as done, which projects exist, what to call them,
  and what is off limits. The files do not contain this. Chapter 1D shows what happens when the
  list of projects is missing or incomplete.
- The agent supplies judgment at a scale you would not spend by hand: reading hundreds of files and
  deciding what each one is.
- Plain code supplies guarantees: exact moves, coverage checks, verification, and undo.

When something goes wrong, it usually means one of the three parties was asked to do another's job.

## Chapters

One row per chapter. Variants and follow-ups sit in the last column.

| # | Chapter | Status | Includes |
|---|---|---|---|
| 0 | [What agents and language models are](chapters/00-getting-started/) | Ready | [0B Setting up your computer](chapters/00-getting-started/setup.md) · [0C Check what the agent says it did](chapters/00-getting-started/checking-claims.md) |
| 1 | [Files and folders](chapters/01-files-and-folders/) | Ready | [1B Local model: LM Studio or Ollama](chapters/01-files-and-folders/1b-local-model/) · [1C Apple's on-device model](chapters/01-files-and-folders/1c-apple-foundation-models/) · [1D Files by project](chapters/01-files-and-folders/1d-projects/) · [1E Keeping it sorted](chapters/01-files-and-folders/1e-schedule/) |
| 2 | Messy text and documents | Planned | |
| 3 | Spreadsheets, PDFs and Word files | Planned | |
| 4 | Email triage (drafts only, never auto-send) | Planned | |
| 5 | Checking websites with a browser agent | Planned | |
| 6 | GUI automation with computer use | Planned | |
| 7 | Scheduling it all | Source notes | [Notes: material cut from Chapter 1E](chapters/07-scheduling/source-notes.md) |
| 8 | Securing git before you publish | Outline | [Outline: hooks, history, and going public](chapters/08-securing-git/OUTLINE.md) |
| 9 | A pre-commit security scan agent | Design note | [Plan: a model that reads your commits](chapters/09-security-reviewer/PLAN.md) |
| 10 | [Vetting skills before you install them](chapters/10-skill-security/) | Ready | [10B Checking automatically at session start](chapters/10-skill-security/10b-session-hook/) · [10C Agents are files, not folders](chapters/10-skill-security/10c-agents/) |
| 11 | An editorial agent: how this book is edited | Source notes | [Notes: when the agent fights back](chapters/11-editor/source-notes.md) |

Also: [Quick reference](QUICK-REFERENCE.md) (every common task in one page) and [House style](STYLE.md).

## Getting started

If you are new to agents, read [Chapter 0](chapters/00-getting-started/README.md) first, then install what the book
needs with [Chapter 0B](chapters/00-getting-started/setup.md). Then get the files, check your setup, and start Claude Code:

```bash
git clone https://github.com/ClaySecAI/agents-for-the-boring-stuff.git
cd agents-for-the-boring-stuff
python3 chapters/00-getting-started/check_setup.py
claude
```

Then open [Chapter 1](chapters/01-files-and-folders/README.md).

## Keeping personal data out of this repository

The chapters are tested on realistic files, and sometimes on real ones. Nothing real belongs in
git, so two layers protect it.

The first is `.gitignore`, which skips practice folders, labels, plans, snapshots, and compiled
helpers. It is only a request, and `git add -f` overrides it.

The second is a pre-commit guard, [`scripts/check_repo_clean.py`](scripts/check_repo_clean.py).
It inspects what is about to be committed and refuses the commit when:

- a file is not on a short allowlist (documentation, source, and one settings file)
- a file is large
- a file contains a home-directory path, an email address, a number shaped like a social
  security number, or a key
- a file contains a term from your private blocklist

The guard never prints what it matched, only where. GitHub runs it again on every push to main
and every pull request, along with a secret scan of the whole history. That copy cannot see your private
blocklist. See [CONTRIBUTING.md](CONTRIBUTING.md) and, for reporting a problem,
[SECURITY.md](SECURITY.md).

Enable it once per clone. Keep your blocklist inside `.git/`, where it is never committed:

```bash
git config core.hooksPath .githooks
echo "your-username" >> .git/private-terms.txt     # names, employer, real filenames you tested with
python3 scripts/test_check_repo_clean.py           # the guard has its own tests
```

Use practice folders for any experiment with real files, and delete them when you finish.
Logs can hold copies as well; [Chapter 1B](chapters/01-files-and-folders/1b-local-model/README.md)
shows an example.

## How this book was made

This book is about working with agents, and an agent helped write it. Claude, an AI model from
Anthropic, working in Claude Code, drafted most of the prose and nearly all of the code and
tests. The human author set the direction, made the design decisions, ran the commands that
needed personal credentials, read the results and decided what to publish.

In practice the work went like this. The author described what a chapter should do. Claude wrote
the agent files, scripts, and drafts, ran experiments on the author's machine and reported what
happened, failures included. The author pushed back, chose between options and approved each
step that touched an account or a real file. Most of the bugs and caveats in the text turned up
by running the code and not by reading it. Several came from the author's questions, such as
what happens when a real Downloads folder replaces the tidy fixture.

Three things follow for you as a reader:

- In the text, "we" means the author and Claude together.
- Results come from single runs on one machine, a MacBook Pro with 24 GB of memory. Run the code
  yourself. The tests exist so that you do not have to take the text's word.
- An editing pass removed common AI-writing habits to make the prose easier to read. It does not
  change who wrote it. The commit history carries a Co-Authored-By line naming Claude.

No independent technical editor or reviewer has checked the text. The real-file experiments in
Chapter 1 ran on a copy of the author's own Downloads folder, and only counts appear in the text.

## Credits

This project is inspired by *Automate the Boring Stuff with Python* by Al Sweigart, published by
No Starch Press (3rd edition, 2025; ISBN 9781718503403). The book's approach to everyday chores
gave this project its topics. The book teaches you to write the code that does the chore. This
project asks how much of the chore an agent can do instead.

- Book page: [nostarch.com](https://nostarch.com/automate-boring-stuff-python-3rd-edition)
- Free online text: [automatetheboringstuff.com](https://automatetheboringstuff.com/), which the
  site offers under a Creative Commons Attribution-NonCommercial-ShareAlike license

This is an independent project. It is not affiliated with, sponsored by, or endorsed by Al
Sweigart or No Starch Press. It reproduces no text, code, figures, or exercises from the book. If
you want to learn Python by writing the automation yourself, buy the book or read it online.

## License

The code and text in this repository are released under the MIT License. See
[LICENSE](LICENSE). The book is a separate work under its own terms.
