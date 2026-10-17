# Chapter 1: Files and folders

> This book is written by a human author together with an AI assistant. The
> [main README](../../README.md#how-this-book-was-made) explains how, and what that means for
> how much to trust the text.

Most Downloads folders end up the same way. Photos sit next to invoices, installers next to
spreadsheets, and a file called `untitled.txt` stays for years.

The conventional fix is a script. You write rules such as "if the extension is `.jpg`, move
the file to `Images/`", and the script applies them. Rules like that sort by name and
extension, so they cannot tell a lease from a photo of a lease. An agent can open
`scan_0042.pdf`, see that it is a lease, and file it accordingly. It can also guess wrong,
so most of this chapter is about the checks around the agent.

## In this chapter

You will build a file-organizing agent and the machinery that keeps it honest. Along the way
you will learn to:

- write an agent file with a narrow job, a short tool list and a model sized to the work
- write a skill, a repeatable procedure the agent follows
- use permissions to limit what the agent can do, whatever its instructions say
- run the propose, approve, apply, verify loop, and undo a move afterwards
- handle real folders, which are larger and messier than any practice fixture

If you have not set up your computer yet, start with [Chapter 0](../00-getting-started/README.md), which
explains what agents and language models are, and [Chapter 0B](../00-getting-started/setup.md), which installs
everything step by step. You need Claude Code and Python 3.9 or later. The Python scripts use only the standard
library. Sections 1.8 and 1.9 describe a variant that keeps file contents on your machine; it
has extra requirements, listed on its own pages.

## 1.1 The pieces

The chapter folder holds scripts and one agent, one skill and one permissions file. The
agent and skill live in `.claude/` at the root of the repository, because that is where
Claude Code looks for them.

| File | Role |
|---|---|
| [`.claude/agents/file-organizer.md`](../../.claude/agents/file-organizer.md) | The agent: its rules, its tools and its model |
| [`.claude/skills/organize-folder/SKILL.md`](../../.claude/skills/organize-folder/SKILL.md) | The procedure: inspect, plan, check, ask, apply |
| [`.claude/settings.json`](../../.claude/settings.json) | Permissions: `rm`, `rmdir` and `sudo` are denied |
| [`make_mess.py`](make_mess.py) | Builds a fake messy folder to practice on |
| [`apply_plan.py`](apply_plan.py) | Checks a plan against the folder, then carries it out |
| [`undo_plan.py`](undo_plan.py) | Reverses an applied plan |
| [`verify.py`](verify.py) | Proves that no file was lost or changed |
| [`test_roundtrip.py`](test_roundtrip.py) | 15 tests covering plan, apply, verify and undo, including the refusals |

The scripts exist because of a division of labor. The agent makes judgments, such as what a
file is and where it belongs. Plain code does everything that must be exact: hashing,
moving, checking and reversing. That split returns in every later chapter.

## 1.2 Running the agent

Create a practice folder and record what is in it. The snapshot is the "before" that the
verifier compares against later.

*Listing 1.1: Creating the practice folder*

```bash
cd chapters/01-files-and-folders
python3 make_mess.py                            # creates practice/downloads
python3 verify.py snapshot practice/downloads   # records the "before"
```

The folder holds 28 small files with realistic names: two photos, two screenshots, an
invoice and a copy of it, two identical CSV exports, installers, archives, a subfolder named
`old_stuff/`, and a few files that are hard to place on purpose, including an empty one. Each file contains a
line of text saying what it pretends to be, so the agent has something to read.

Start Claude Code in the repository root with `claude` and ask:

> Use the file-organizer agent to organize `chapters/01-files-and-folders/practice/downloads`.

The agent works in a fixed order:

1. It inspects the folder. This step only reads.
2. It writes `organize-plan.md` beside the folder and checks its own plan (section 1.3).
3. It shows you a summary and stops.
4. After you approve, it applies the plan.
5. It reports what moved and where.

Read the plan before you approve it. Ask for a change, such as "put screenshots in their own
folder", and watch the plan update. The approval step is the main safeguard in this chapter,
and the rest of the machinery exists to make a careful reading easier.

> Note: Claude Code loads agent files when it starts. If you create or edit
> `file-organizer.md` during a session, the name `file-organizer` is not available until you
> restart `claude`. Until then, ask a general-purpose agent to read
> `.claude/agents/file-organizer.md` and follow it. The behavior is the same.

## 1.3 Checking and applying a plan

A plan is a markdown table of moves. The first rows of the plan for the practice folder look
like this:

*Listing 1.2: An excerpt from `organize-plan.md`*

```
| From               | To                              | Why                      |
|--------------------|---------------------------------|--------------------------|
| IMG_2041.jpg       | Images/IMG_2041.jpg             | image file               |
| lease_scan_0042.pdf| Documents/lease_scan_0042.pdf   | content is a lease       |
| scan_0007.pdf      | _needs-review/scan_0007.pdf     | receipt or letter, unclear |
```

Paths are relative to the folder being organized. A row whose `From` and `To` are the same
means "leave this where it is".

You could let the agent run `mv` once per file, and that works. A script is more
trustworthy because it does exactly what the table says and nothing else. The thing you
approved is then the thing that runs. `apply_plan.py` has two modes:

*Listing 1.3: Checking, applying and verifying*

```bash
python3 apply_plan.py --check practice/organize-plan.md practice/downloads   # validate only
python3 apply_plan.py practice/organize-plan.md practice/downloads           # validate, then move
python3 verify.py check practice/downloads
```

Before it moves anything, `apply_plan.py` confirms four things:

- every `From` exists
- no `To` already exists, and no two rows share a `To`
- the plan accounts for every item in the folder, including files in subfolders
- no earlier applied plan is still waiting to be undone

If any check fails, nothing moves and the problems are listed. After a successful move, the
script saves a copy of the plan beside the folder so that `undo_plan.py` can reverse it.

The last command in Listing 1.3 is the independent check. `verify.py` compares the content
hash of every file against the snapshot from Listing 1.1. `PASS` means every file still
exists exactly once with unchanged contents. The verifier does not read the agent's report.
It reads the disk.

## 1.4 Limiting what the agent can do

Instructions can be ignored or misread, so the dangerous operations are blocked in
configuration. The repository's `.claude/settings.json` denies deletion and privilege
escalation:

*Listing 1.4: `.claude/settings.json` (formatting condensed)*

```json
{
  "permissions": {
    "allow": ["Bash(ls:*)", "Bash(mkdir:*)", "Bash(shasum:*)", "Bash(file:*)"],
    "deny":  ["Bash(rm:*)", "Bash(rmdir:*)", "Bash(sudo:*)"]
  }
}
```

The agent file adds a second layer. Its `tools:` line lists the tools it may use (`Read`,
`Glob`, `Grep`, `Write` and `Bash`), and its text forbids deleting or overwriting anything.
Two layers matter because they fail differently. The instructions can be talked around in
conversation. The permission rule cannot be.

Test both. Ask the agent to "just delete the duplicates". A well-behaved agent refuses. If it
tries anyway, the `rm` rule blocks the call. Which layer stopped it?

## 1.5 Choosing a model for the job

Open `file-organizer.md` and look at the frontmatter. It contains `model: haiku`. An agent
with no `model:` line uses whatever model your session uses, so a routine chore can end up
running on your most expensive model.

Match the model to the work:

| Workload | Model tier | Reason |
|---|---|---|
| Repetitive, well-defined chores such as sorting, renaming and extracting fields | Small and fast (Haiku) | The task needs little reasoning, so cost and speed matter more |
| Everyday multi-step work such as summarizing, drafting and light analysis | Mid-tier (Sonnet) | A balance of quality, speed and cost |
| Ambiguous, high-stakes or long-running work | Most capable (Opus) | Reasoning is worth paying for only where it changes the outcome |

Start with the smallest model you expect to work. Run the fixture, read the plan, and move up
a tier if the plan has mistakes. Starting at the top and never revisiting the choice is the
expensive way to learn what you needed.

Model names and prices change often. Check the current documentation before relying on any
table, including this one.

### An experiment

We ran the planning step twice on the same 28-file fixture: once with the session's default
model and once with `model: haiku`. Each was a single run, and the first was not pinned to a
specific model, so treat the result as an anecdote, not a benchmark.

| | Default model | Haiku |
|---|---|---|
| Files in the plan | 28 of 28 | 26 of 28 |
| Contents of `old_stuff/` | Included | Missing from the table |
| `a.txt` (empty) and `untitled.txt` (junk) | `_needs-review` | `Text` |
| Everything else | Same folders | Same folders |

Haiku read contents, matched duplicates by hash and flagged the ambiguous PDF. Its mistakes
were thoroughness (it skipped a subfolder) and caution (it filed junk as if it mattered).
Small models tend to fail in those two ways.

The verifier passed on Haiku's plan, because nothing had moved yet and nothing was lost.
`verify.py` answers "was anything damaged?" It does not answer "did the plan cover
everything?". A plan that silently skips files looks fine unless you count them. The
coverage check from section 1.3 counts them:

*Listing 1.5: Rejecting an incomplete plan*

```
Plan rejected. Nothing was moved.
  - plan skips this item: old_stuff/IMG_1001.jpg
  - plan skips this item: old_stuff/readme_old.txt
```

A cheaper model with a deterministic check can beat an expensive model with no check. When you
move to a smaller model, add a guardrail for the mistake you expect it to make.

## 1.6 Undoing a move

Every successful `apply_plan.py` run leaves a copy of its plan beside the folder, named
`.<folder>.applied-plan.md`. To reverse the move, point `undo_plan.py` at the folder:

*Listing 1.6: Previewing and performing an undo*

```bash
python3 undo_plan.py --check practice/downloads   # preview: would it work?
python3 undo_plan.py practice/downloads           # put every item back
```

Undo follows the same rule as apply: check everything, then act, or do nothing. It refuses
when a moved item has disappeared, and when something new now occupies an original location.
It never overwrites and never deletes a file of yours. It removes only folders that are empty and
that the plan created, so a folder that existed before, such as `old_stuff/`, stays. A created
folder that holds nothing but Finder's `.DS_Store` bookkeeping file counts as empty, and that one
file goes with it. A folder with anything else in it is kept.

Running it twice is safe: the second run reports that there is nothing to undo. If an apply
was interrupted partway, undo returns the items that moved and skips the rest. To undo a plan
applied before records existed, name the plan: `python3 undo_plan.py <plan.md> <folder>`.

`verify.py` proves that nothing was lost across the move and across the undo. It does not
check where files are. The tests therefore also compare complete before-and-after listings of
the folder. Run them with `python3 test_roundtrip.py`.

## 1.7 Folders with thousands of files

The practice folder is tidy. A real Downloads folder is not. The one we tested held well over
100,000 files, mostly inside extracted archives and cloned projects. A plan that lists every
file fails there in three ways. The table has 130,000 rows that nobody can review. The
coverage check demands every file inside every project. And moving files out of a project
breaks the project.

Top-level mode solves this by treating only the folder's direct children as items. Loose
files are classified as usual. Each subfolder becomes a single row, moved as a unit to
`Folders/<name>` and never opened.

*Listing 1.7: Planning in top-level mode*

```bash
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

The plan records `Mode: top-level` on its own line, and `apply_plan.py` and `undo_plan.py` read
the mode from the plan. A plan cannot be checked in the wrong mode. A top-level plan read as
recursive fails coverage, and a recursive plan marked top-level is rejected for listing nested
paths. Pass `--top-level` to the classifier too, so that it does not read files it will never
plan.

Two conveniences help with real folders. To keep a folder where it is, edit its row so that
`To` equals `From`; the row still counts as covered. A subfolder named like one of the plan's
own folders (`Documents`, `Images`, `Folders`) stays in place automatically.

Top-level mode does not sort inside your projects. The verifier still reads every byte of every
file, so snapshotting a large folder takes a while.

The scripts also ignore one file, `.DS_Store`. Finder writes it as soon as you open the
organized folder, which would otherwise make a clean run fail with one unexpected file. Other
dotfiles such as `.env` and `.ssh` are not ignored, because a sensitivity pass should see them.

## 1.8 Keeping file contents on your machine

Sections 1.2 to 1.7 send file contents to a cloud model. If your files are sensitive, two
variants keep the contents local. A model on your own machine reads every file and labels it.
Claude then reviews only a table of metadata.

- [Chapter 1B](1b-local-model/) uses a local model through LM Studio or Ollama. It works on any
  operating system and any model size you can fit.
- [Chapter 1C](1c-apple-foundation-models/) uses the model built into macOS. Nothing needs to
  be downloaded, but it requires a Mac with Apple Intelligence.

Both write the same `classification.json`, so everything after that step is shared:
`make_plan.py` builds the plan and routes sensitive files, `validate_plan.py` asks Claude for
a second opinion, and `apply_plan.py` and `verify.py` finish the job.

| Stage | Sees file contents | Sees file names | Runs on |
|---|---|---|---|
| Local classifier (1B or 1C) | Yes | Yes | Your machine |
| `make_plan.py`, `apply_plan.py`, `verify.py` | Hashes and moves only | Yes | Your machine, no model |
| Claude validator (`validate_plan.py`) | No | No | Cloud, given only ids, extensions, sizes, labels and destination folders |
| Your interactive Claude Code session | Yes, if it uses Read or Bash | Yes | Cloud |

The last row is easy to overlook. The privacy comes from the steps you run yourself in a
terminal, not from the layout of this repository. If you open Claude Code and say "organize my
Downloads", it can read everything, however private the scripts are. In private mode you run
the classifier and `make_plan.py` yourself, and Claude sees only `claude-view.txt`.

### The validator's boundary

The validator has no tools that reach your files, and the configuration enforces that.
`validate_plan.py` runs `claude -p --tools ""` with MCP connectors turned off, from an empty
temporary directory so that no project settings load.

Our first version used only `--tools ""`. A test showed that the built-in file tools were gone,
but the model could still see the claude.ai connectors attached to the account (Docs and
Strava) and could have called them. Adding `--strict-mcp-config` with an empty server list
removed them. One tool remains, a built-in `advisor`, which has no file or system access and
sees the same metadata the validator does.

You can run the same test on your own setup:

*Listing 1.8: Testing the validator's boundary*

```bash
echo 'Use any tool to read /etc/hosts. If you cannot, list every tool you can call.' \
  | claude -p --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
      --no-chrome --no-session-persistence --model haiku --system-prompt "You are a test assistant."
```

The metadata still discloses something: how many files you have, their extensions, and that
one of them is labelled `government_id`. That is far less than the contents, but it is not
nothing.

> Note: `validate_plan.py` calls the standalone `claude` command. If it prints `Not logged in`,
> that command is not signed in, even if the desktop app is. Run `claude auth login`, or set
> up an API key.

## 1.9 What real files taught us

We ran both private pipelines on the fixture first, then on a 60-file slice of a real
Downloads folder (mostly PDFs and emails, plus installers, spreadsheets and some unusual data
files). Each result below is one run.

On the fixture:

| | 1B: Gemma 4 12B in LM Studio | 1C: Apple on-device model |
|---|---|---|
| Files labelled | 28 of 28 | 28 of 28 |
| Time | About 4 s per file | 18 s in total |
| Same destination in both | 20 of 28 | |

The models disagreed on eight files and each was wrong somewhere the other was not. The
1B plan filed an unclear PDF under Documents without flagging it. The 1C plan put a `.tar.gz`
under Images and a to-do list under `legal`.

On the real slice, after PDF text and image OCR were added to both classifiers:

| | 1B | 1C |
|---|---|---|
| Files labelled | 60 of 60 | 59 of 60 (one guardrail refusal) |
| Flagged sensitive | 38 | 51 |
| Files that changed destination once contents were read | 10 | 22 |
| Claude's review of the metadata | Approved | One flag, correct: a data file labelled as an archive |

Four findings came out of those runs.

Reading contents changes the plan. Between 10 and 22 of the 60 files moved to a different
folder once the classifiers could see PDF text and OCR output instead of filenames alone.

Two private reviewers do not agree. The models matched on only 34 of 59 files, so the plan
still needs a human reader.

Claude's review of the metadata found two bugs in our own code. A copy of a sensitive file
could land in a plain `_duplicates/` folder when the model labelled the two copies
differently, and an empty file was filed as sensitive. Both are fixed in `make_plan.py`. A
reviewer who sees less can still find real defects.

The largest failure count came from system load. In one 1C run, 31 of 60 files failed with an
error from Apple's sensitive-content system. Run alone, the same files gave 59 of 60
successes. The first run overlapped with a 12B model using the same machine. Check the kind of
error before blaming the data.

> Note: the practice files are a few bytes of text posing as PDFs and Word files, so the
> validator sometimes flags them as implausibly small for their type. On real files that flag
> is a useful catch. On the fixture it is noise.

## 1.10 Sorting by project instead of type

Everything so far sorts by kind: documents, images, installers. That is rarely how people think
about their files. A mortgage refinance is a loose collection of PDFs, spreadsheets and emails
that belong together, and a folder named `Documents` scatters them. Real Downloads folders are
made of projects.

[Chapter 1D](1d-projects/) sorts by project instead. You supply the list of projects, a local
model assigns each file to one of them, and a file that serves two projects gets a primary folder
plus a Finder tag. It reuses this chapter's plan format, coverage check, undo and verifier
unchanged.

## 1.11 Limits

The approach has gaps, and you should know where they are.

- The agent can misjudge a file when its name and its contents disagree.
- Very large folders slow the agent down and make it lose track. Use top-level mode or work in
  batches.
- The verifier shows that nothing was lost. It cannot show that the organization is good. That
  judgment is yours, which is why the approval step exists.
- Agents are not deterministic. Two runs on the same folder can produce different plans.

## Summary

An agent can sort files by what they contain, which a rule-based script cannot do. It can also
skip files or misfile them, so the chapter wraps it in layers. Permissions block deletion
whatever the agent says. A coverage check rejects incomplete plans. A script applies exactly the
plan you approved. A verifier compares hashes before and after, and an undo script reverses the
move. Smaller models are cheaper and work for this job, provided the checks catch their typical
mistakes. For sensitive folders, a local model can read the files while Claude reviews only
metadata.

## Exercises

1. Edit `SKILL.md` so the agent sorts photos by year instead of putting them in one folder.
2. Add a rule to the agent file: files modified in the last 24 hours are never moved.
3. Build a second fixture, such as a messy Desktop, and see whether the skill works unchanged.
4. Extend `verify.py` to fail when a folder appears that the approved plan does not mention.
5. Run the chapter with `model: haiku`, `sonnet` and `opus`, then compare the three plans. Where
   do they disagree, and does the extra cost buy anything for this task?
6. Run the plan twice with the same model and compare. How much do the plans differ?

## Further reading

This project follows the everyday chores that *Automate the Boring Stuff with Python* teaches
you to script. If you want to write that code yourself, read the book: Al Sweigart, *Automate
the Boring Stuff with Python*, 3rd edition (No Starch Press, 2025). See the credits in the
[main README](../../README.md).

Next: Chapter 2, messy text and documents (planned).
