# Chapter 1: Files and Folders

**The chore:** your Downloads folder is a landfill. Photos, invoices, installers and
files called `untitled.txt` are all mixed together.

**The old way:** write a script with rules like "if the extension is `.jpg`, move it to
`Images/`".

**The agent way:** point an agent at the folder and say "tidy this". An agent can read a
file called `scan_0042.pdf` and see it's a lease, which no extension rule can do. But it
can also guess wrong, so we put guardrails around it.

## What you'll learn

- Writing an **agent file** with a narrow job, a short list of tools, and the right-sized model
- Writing a **skill**, a repeatable procedure the agent follows
- Using **permissions** to limit damage (`.claude/settings.json`)
- The **propose, approve, apply, verify** loop

## What's in the box

| File | Role |
|---|---|
| [`.claude/agents/file-organizer.md`](../../.claude/agents/file-organizer.md) | The agent: its rules and personality |
| [`.claude/skills/organize-folder/SKILL.md`](../../.claude/skills/organize-folder/SKILL.md) | The procedure: inspect, plan, approve, apply |
| [`.claude/settings.json`](../../.claude/settings.json) | Guardrails: `rm` is denied outright |
| [`make_mess.py`](make_mess.py) | Builds a fake messy folder to practice on |
| [`apply_plan.py`](apply_plan.py) | Validates the plan (covers every file?), then executes it exactly |
| [`undo_plan.py`](undo_plan.py) | Reverses an applied plan: every item back where it came from |
| [`test_roundtrip.py`](test_roundtrip.py) | 13 tests: plan, apply, verify, undo, and every way they should refuse |
| [`verify.py`](verify.py) | Proves no file was lost or changed |

## Try it

From the repo root:

```bash
cd chapters/01-files-and-folders
python3 make_mess.py                      # create practice/downloads
python3 verify.py snapshot practice/downloads   # record the "before"
```

Start Claude Code in the repo root (`claude`) and ask:

> Use the file-organizer agent to organize `chapters/01-files-and-folders/practice/downloads`.

You should see this sequence:

1. The agent inspects the folder (reading, no changes).
2. It writes `organize-plan.md` beside the folder and shows you a summary.
3. **It stops and waits.** Read the plan. Try asking it to change something, such as
   "put screenshots in their own folder".
4. After you approve, the plan gets applied (see "Applying the plan" below).
5. It reports what it did.

> **Heads up:** Claude Code loads agent files when it starts. If you create or edit
> `file-organizer.md` mid-session, the `file-organizer` name won't exist until you
> restart `claude`. Until then, ask a general-purpose agent to "act as the
> file-organizer agent: read `.claude/agents/file-organizer.md` and follow it".
> The behavior is the same. The name just isn't registered yet.

## Applying the plan

You could let the agent run `mv` for each file, and it works. But there's a more
trustworthy option: [`apply_plan.py`](apply_plan.py) reads the plan's table and
performs exactly those moves, nothing more. It validates first (every file covered, no
overwrites, no missing sources), so a bad plan moves nothing.

```bash
python3 apply_plan.py --check practice/organize-plan.md practice/downloads   # validate only
python3 apply_plan.py practice/organize-plan.md practice/downloads           # validate, then move
```

Why bother? Reading the plan is the review step, so the thing you approved should be the
thing that runs. A script makes that literal: no improvising, no extra steps, and it
refuses to overwrite anything or continue past a missing file. The agent does the
judgment (what is this file?), and a dumb, predictable script does the doing.
That split of judgment for the agent and execution for deterministic code comes back in
later chapters.

Then check its work:

```bash
python3 verify.py check practice/downloads
```

`PASS` means every file still exists, once, with unchanged content. The verifier
doesn't trust the agent's report. It re-reads the disk.

## Tip: use the right model for the workload

Open `file-organizer.md` and look at the frontmatter: `model: haiku`. Without that
line, an agent inherits whatever model your session is using. That's convenient, but it
means a chore like sorting files might run on your most expensive model.

A rough rule of thumb:

| Workload | Model tier | Why |
|---|---|---|
| Repetitive, well-defined chores (sorting, renaming, extracting fields) | Small and fast (Haiku) | Cheap and quick; the task doesn't need deep reasoning |
| Everyday multi-step work (summarizing, drafting, light analysis) | Mid-tier (Sonnet) | A good balance of quality, speed and cost |
| Ambiguous, high-stakes or long-horizon work (complex planning, tricky judgment calls) | Most capable (Opus) | Pay for reasoning only where it changes the outcome |

How to apply it:

- Set `model:` on each agent file based on what that agent actually does.
- Start with the smallest model you think could work, run the fixture, and check the
  plan and the verifier. If it makes mistakes, move up a tier. Don't start at the top
  and never look back.
- Remember that the verifier checks that nothing was lost, not that the sorting is
  good. Judge the quality of the plan yourself when comparing models.
- Because the approval step is a safety net, a cheaper model is a safer bet here
  than in a fully unattended workflow.

### A real comparison

We ran the plan step twice on the same 28-file fixture: once with the session's default
model, and once with `model: haiku`. (Single runs, and the first wasn't pinned to a
model, so treat this as an anecdote, not a benchmark.)

| | Default model | Haiku |
|---|---|---|
| Files in the plan | 28 of 28 | **26 of 28** |
| `old_stuff/` subfolder | Included | **Skipped, never mentioned in the plan table** |
| `a.txt` (empty), `untitled.txt` (junk) | `_needs-review` | Text |
| Everything else | Same categories | Same categories |

Haiku got 24 of 28 files right and did the hard part fine: it read contents, matched
duplicates by hash, and flagged the ambiguous PDF. Its mistakes were about
**thoroughness** (it missed a subfolder) and **caution** (it filed junk as if it
were meaningful). Those are exactly the failures a cheap model is most prone to.

And notice what did not catch it: `verify.py` passed, because nothing was lost.
The verifier answers "was anything damaged?", not "did the plan cover everything?".
A plan that silently skips files looks fine unless you count.

That's why `apply_plan.py --check` exists. It rejects any plan that doesn't account
for every file on disk, and you can run it before approving:

```bash
python3 apply_plan.py --check practice-haiku/organize-plan.md practice-haiku/downloads
# Plan rejected. Nothing was moved.
#   - plan skips this file: old_stuff/IMG_1001.jpg
#   - plan skips this file: old_stuff/readme_old.txt
```

**The lesson:** a cheaper model plus a deterministic check can beat an expensive model
with no check. When you downgrade a model, add a guardrail for the failure you'd
expect it to make.

Try it: run the chapter with `model: haiku`, then `sonnet`, then `opus`, and diff the
`organize-plan.md` each produces. Where do they disagree? Is the extra cost buying
anything for *this* task? (Model names and pricing change, so check the current model
docs rather than trusting any table, including this one.)

## Things worth poking at

- **Ambiguity.** Where did `scan_0007.pdf`, `a.txt` and `random.bin` end up? Did the
  agent put them in `_needs-review/` or guess? Is that what you'd want?
- **Duplicates.** `invoice_march.pdf` and `invoice_march (1).pdf` are identical, as
  are the two `export` CSVs. The agent should catch them by content, not name.
- **The nested folder.** Did it handle `old_stuff/`? Should it have?
- **Try to break it.** Ask it to "just delete the duplicates". It should refuse, and
  if it tries, the `rm` deny rule should stop it. Which layer caught it, the agent's
  instructions or the permissions? You want both.
- **Run it twice.** Do you get the same layout? Agents are not deterministic, which
  is why we verify outcomes and don't assume them.

## Undo

Every successful `apply_plan.py` saves a copy of the plan beside the folder
(`.<folder>.applied-plan.md`). To reverse a move:

```bash
python3 undo_plan.py practice/downloads            # puts every item back
python3 undo_plan.py --check practice/downloads    # preview: would it work?
```

Undo follows the same rule as apply: **check everything first, then act, or do nothing**.
It refuses if a moved item has vanished, or if something new now sits at an original
location (it will not overwrite it). It deletes no files. It only removes folders that are
empty and that the plan created, so a folder that existed before, like `old_stuff/`, stays.
You can run it twice safely: the second time says there's nothing to undo. If an apply was
interrupted halfway, undo puts back what moved and skips the rest.

Applied something before this existed? Name the plan yourself:
`python3 undo_plan.py <plan.md> <folder>`.

`verify.py` still has the last word. It proves nothing was lost or changed after the move
*and* after the undo. It doesn't check *where* things are, so the tests also diff full
before-and-after listings of the folder. Run them with `python3 test_roundtrip.py`.

## Real folders: top-level mode

A real Downloads folder doesn't look like the fixture. Ours held **well over 100,000 files**, mostly
inside extracted archives and cloned projects. A per-file plan fails there in three ways:
a 130,000-row table nobody can review, a coverage check that demands every file in every
project, and moving files out of a project, which breaks the project.

**Top-level mode** treats only the folder's direct children as items. Loose files are
classified as usual. **Each subfolder becomes one row, moved as a unit to `Folders/<name>`
and never opened.**

```bash
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

The plan records `Mode: top-level` on its own line, and `apply_plan.py` and `undo_plan.py`
read the mode from the plan. A plan can't be checked in the wrong mode: a top-level plan
read as recursive fails coverage, and a recursive plan marked top-level is rejected for
listing nested paths. Run the classifier with `--top-level` too, so it doesn't read the
130,000 files it will never plan.

Two small conveniences:

- **Keep a folder where it is** by editing one cell so `To` equals `From`. The row still
  counts as covered. Don't delete the row, which would fail the coverage check.
- **A folder named like one of the plan's own** (`Documents`, `Images`, `Folders`...) is left
  in place automatically, and loose files may be added to it.

What top-level mode doesn't do: it won't sort *inside* your projects, and snapshotting
11 GB with `verify.py` takes minutes (it still hashes everything). Both are deliberate.

### Also ignored: `.DS_Store`

Finder writes a `.DS_Store` file the moment you open the organized folder to look at it,
which would make a clean run "fail" with one unexpected file. The scripts ignore that one name.
Other dotfiles (`.env`, `.ssh`...) are not ignored, since those are what a sensitivity pass
should catch.

## Going further: private mode (1B and 1C)

Everything above sends file contents to a cloud model. If your files are sensitive,
there's a variant where a model **on your own machine** reads them, and Claude only
reviews a table of metadata:

- [**1B**: a local model through LM Studio or Ollama](1b-local-model/): any size you can fit, any OS.
- [**1C**: Apple's built-in on-device model](1c-apple-foundation-models/): nothing to download, Apple Intelligence Macs only.

Both produce the same `classification.json`, so everything after that step is shared:
`make_plan.py` (plan + DLP routing), `validate_plan.py` (Claude, no tools),
`apply_plan.py`, `verify.py`.

### Who sees what

| Stage | File contents? | File names? | Runs |
|---|---|---|---|
| Local classifier (1B or 1C) | Yes | Yes | Your machine |
| `make_plan.py`, `apply_plan.py`, `verify.py` | Yes (hashes, moves) | Yes | Your machine, no model |
| **Claude validator** (`validate_plan.py`) | **No** | **No** | Cloud. It gets ids, extensions, byte sizes, labels and destination folders |
| **Your interactive Claude Code session** | **Yes, if it uses Read or Bash** | Yes | Cloud |

That last row is the one people miss. The privacy comes from the **steps you run
yourself in a terminal**, not from this repo's folder layout. If you open Claude Code and
say "organize my Downloads", it can read everything, however private the scripts are.
In private mode, run the classifier and `make_plan.py` yourself, and let Claude see only
`claude-view.txt`.

The privacy boundary is enforced by tools, not by asking nicely: `validate_plan.py` runs
`claude -p --tools ""` with MCP connectors switched off, so the validator has **no tool
that can touch your files**. It also runs from an empty temp directory so no project
settings load.

**We almost got this wrong.** Our first version used only `--tools ""`. Testing it
(ask the model to read `/etc/hosts` and list its tools) showed the built-in file tools
were gone, but the model could still see our claude.ai connectors (Docs, Strava) and
could have called them. Adding `--strict-mcp-config --mcp-config '{"mcpServers":{}}'`
removed them. The one thing left is a built-in `advisor` tool, which has no file or system
access and sees only the same metadata. **Test your boundary yourself** the same way:

```bash
echo 'Use any tool to read /etc/hosts. If you cannot, list every tool you can call.' \
  | claude -p --tools "" --strict-mcp-config --mcp-config '{"mcpServers":{}}' \
      --no-chrome --no-session-persistence --model haiku --system-prompt "You are a test assistant."
```

A boundary you haven't tried to break is a hope, not a boundary.

Even the metadata says something: a count of files, their extensions, and the fact that
you own a `government_id` file. That's a much smaller disclosure than contents, but it
isn't zero.

### A real comparison (28-file fixture, one run each)

| | 1B: Gemma 4 12B (LM Studio) | 1C: Apple on-device |
|---|---|---|
| Files labelled | 28 of 28 | 28 of 28 |
| Time | about 4 s per file (reasoning off) | 18 s total |
| Agreement between the two | 20 of 28 files in the same folder | |
| Mistakes we saw | `scan_0007.pdf` (unclear) filed under Documents, unflagged | `.tar.gz` under Images, to-do list under `legal`, plain CSVs as financial |

Neither is clearly better. They disagreed on 8 files, and each was wrong somewhere the
other wasn't. That's the case for a second reviewer, and for the metadata check by Claude:
in our test it caught the `.tar.gz`-as-Images clash from extension and category alone,
and it added noise (it also flagged an empty file in `_needs-review`, which is correct
routing), so we tightened its prompt. A weak local model plus a deterministic plan check
plus a metadata-only second opinion is a reasonable stack. None of the three is enough alone.

### What happened on real files (60 files from a real Downloads folder)

The fixture is tidy. A real folder isn't. We ran both private pipelines on a 60-file slice
(mostly PDFs and emails, plus installers, spreadsheets and some odd data files) and learned more than the fixture taught:

| | 1B (Gemma 12B) | 1C (Apple) |
|---|---|---|
| Labelled | 60 of 60 | 59 of 60 (1 guardrail refusal) |
| Flagged sensitive | 38 | 51 |
| Changed destination once PDFs and images were *read* | 10 files | 22 files |
| Claude's metadata review | approve | 1 flag, correct: a specialist data file labelled Archives |

- **Reading content changes a lot.** With filename-only judging, 10 to 22 of the 60 files
  landed somewhere different once PDF text and OCR were available.
- **The two local models agreed on only 34 of 59 files.** Two private reviewers are not
  redundant, they disagree. The plan needs a human read.
- **Claude's metadata-only review found two bugs in our own code,** not just in the
  models' labels: a copy of a sensitive file could escape to a plain `_duplicates/` folder when
  the model labelled the two copies differently, and an empty file was filed as sensitive.
  Both fixed in `make_plan.py`. A reviewer with less information still found real defects.
- **Check which error you're seeing.** Our worst result (31 of 60 failing) was load, not
  content.

> **Fixture caveat:** the practice files are a few bytes of text pretending to be PDFs and
> Word files, so the validator sometimes flags them as "impossibly small" for their
> type. On real files that flag would be a good catch. Here it is noise from the fixture.

> **Heads up:** `validate_plan.py` calls the standalone `claude` CLI. If it says
> `Not logged in`, that CLI isn't authenticated (the desktop app signs in separately).
> Run `claude` once in a terminal to log in, or set up an API key, then try again.

## Where this breaks

- It guesses wrong about a file's purpose when the filename and contents disagree.
- On huge folders (thousands of files) it will be slow and may lose track. Work in batches.
- A verifier can show nothing was lost, but not that the organization is *good*.
  That part is still your judgment, and it's why the approval step exists.

## Exercises

1. Edit `SKILL.md` so the agent sorts photos by year instead of lumping them into one folder.
2. Add a rule to the agent file: files modified in the last 24 hours are never moved.
3. Make a second fixture (a messy Desktop) and see whether the skill works unchanged.
4. Extend `verify.py` to also fail if any folder is created that isn't in the approved plan.

Next: Chapter 2, messy text and documents *(coming soon)*.
