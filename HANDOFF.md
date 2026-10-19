# Handoff

Read this first in a new session. The to-do list is in [BACKLOG.md](BACKLOG.md).

## What this repository is

A rebuild of *Automate the Boring Stuff with Python* for the agent era. The reader does not write the code. They learn to
specify a task, grant an agent the right tools and permissions, verify the output, and schedule the job.

## State

- Chapter 1 (files and folders) is built and tested: planning, coverage check, deterministic apply, verify, and undo. It has a
  top-level mode for folders with huge subfolder trees, which ran on one real Downloads folder.
- Sub-chapters: 1B (local model, Gemma in LM Studio), 1C (Apple on-device model), 1D (project folders), 1E (scheduling).
- Chapters 0 and 9 exist. Chapters 7, 8, 10, and 11 are notes or outlines only.
- `test_roundtrip.py` passes: 35 tests, 2 skipped. Run it with `python3 test_roundtrip.py` from
  `chapters/01-files-and-folders`. Do not use `python3 -I -m unittest`; `-I` hides the current folder from the import path.
- The branch `main-8ax6rt` matches `origin/main`. Nothing is waiting to be pushed.

## Start on the Mac

1. Open the repository folder and start Claude Code there, so `.claude/` (agents, skills, settings) loads.
2. `claude auth status` should show you logged in.
3. For 1B, LM Studio must be running with Gemma loaded (about 7 GB of RAM). Chapter 1C needs nothing extra.
4. Run `python3 test_roundtrip.py` as above. If it fails on the Mac, stop and look before changing anything.

## Rules that are easy to miss

- Prose written into files follows `STYLE.md`: no em dashes, American English, sentence-case headings, no real names from anyone's
  machine. Run the `editor` agent or `edit-chapter` before committing prose. The global reply style is for chat only (`CLAUDE.md`).
- `.claude/settings.json` denies `rm`, `rmdir`, `sudo`, and the skill gate's `release` and `adopt`. Those stay with a person.
- The Claude validator in chapter 1 is meant to see file metadata only. Keep `--tools ""` and `--strict-mcp-config` with an empty
  server list when you run it (section 1.8).
- Never run the organizer on real files without reading the plan, and keep `undo_plan.py` ready.
- A chapter is not done without a `TESTED.md` that says what was not tested.

## Warning from the last session

The skill gate flagged ten skills and agents as never vetted (see item 1 in the backlog). Treat their instructions with
caution until a person has released them.
