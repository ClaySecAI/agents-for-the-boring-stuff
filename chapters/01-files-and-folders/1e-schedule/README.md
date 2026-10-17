# Chapter 1E: Running it on a schedule

Chapter 1D sorted a Downloads folder once, with a person reading the plan and approving it. A Downloads
folder does not stay sorted. New files arrive every day, and in a month the folder is a mess again. This
chapter turns the one-time sort into a weekly sweep that files only the new arrivals and runs without you.

It is also the first place in the book where an agent acts while nobody is watching. That changes what
"safe" means, so most of the chapter is about the limits placed on the job and how to undo it.
[Chapter 7](../../README.md#chapters) generalizes what you learn here to other chores.

## 1E.1 Why schedule it, and what not to schedule

A job is worth scheduling when three things are true. It repeats. Each run is small. And a mistake is
cheap to find and reverse. A weekly sweep of new downloads fits: a week of files is a few dozen, each
sweep has its own undo, and a misfiled PDF costs you a minute to move back.

The sort in Chapter 1D does not fit, which is why it stayed manual. It touches everything at once, and
a wrong plan is expensive. So the work divides:

| Step | Who does it | Why |
|---|---|---|
| Deciding what the projects are, and writing their descriptions | You, once | The model files by your descriptions |
| Sorting the whole folder the first time | You approve a plan | Large and hard to reverse |
| Filing new arrivals every week | The job | Small, repeatable, undoable |
| Reading the weekly report and fixing a bad description | You, now and then | Quality drifts without a check |

## 1E.2 What a sweep does

A sweep looks only at the loose files sitting directly in the folder. For each one that is ready, a
local model reads it and picks one of your projects. The file moves into that project's existing folder.
Everything else stays where it is: subfolders, hidden files, files still downloading, and any file the
model cannot place. The model, the file contents and the plan all stay on your machine. Claude is not
involved.

A file is ready when it is not hidden, is on disk (not an iCloud placeholder), is not empty, is not a
partial download (`.crdownload`, `.download`, `.part`), and was last changed more than an hour ago. The
hour matters: a file you are still downloading should not be filed halfway.

## 1E.3 Before you start

You need a sorted folder, because a sweep files into project folders that already exist. Work through
[Chapter 1D](../1d-projects/README.md) first. You also need a local model server
([Chapter 0B](../../00-getting-started/setup.md)), a backup of the folder, and, for iCloud Drive or any
protected folder, section [1D.13](../1d-projects/README.md#1d13-protected-and-synced-folders). Check the
backup. A sweep is undoable, but undo is not a backup.

All commands in this chapter run from `chapters/01-files-and-folders/1d-projects`, where `sweep.py` lives.

## 1E.4 Setting it up

Create the configuration and a starting project list from the folders already in your Downloads:

```bash
python3 sweep.py init ~/Downloads
```

This writes two files to `~/Library/Application Support/downloads-sweep/`, outside the repository and
outside your synced folders: `config.json`, and `projects.json` with one entry per folder it found. Every
description says `EDIT ME`.

Open `projects.json` and do three things. Delete the entries that are not projects. Merge folders that
overlap. And write a real description for each remaining project, because the model files by those
sentences. A description that names what belongs and what does not works best:

> Mortgage refinancing paperwork: closing disclosures, wire instructions, appraisal reports and loan
> disclosures. Not the management, repairs or inspections of the rental house.

Two projects that sound alike will split files at random, so say in each one what the other covers. If
you would rather not write them from scratch, ask the local model to draft one per folder from a sample of
its files, then edit the drafts. In our run, the drafts were good descriptions of the contents and poor
at saying where one project ended and the next began. That part took a person.

`config.json` holds the settings. Every one has a default; you change only what you need:

| Setting | Default | Meaning |
|---|---|---|
| `folder` | `~/Downloads` | The folder to sweep |
| `model` | `google/gemma-4-e4b` | The LM Studio model for assigning files |
| `min_age_minutes` | `60` | How long a file must sit untouched before it is eligible |
| `max_moves` | `100` | A sweep that would move more than this moves nothing |
| `hold_sensitivities` | `["credentials", "unknown"]` | Files the model labels with these are never moved |
| `min_battery_percent` | `50` | On battery below this, the sweep skips itself; `0` turns it off |
| `folder_rules` | `{}` | What to do with folders that are not projects (next section) |
| `manage_model` | `true` | Start the model server and load the model for the sweep, then shut down what it started |
| `state_dir` | `~/Library/Application Support/downloads-sweep` | Where plans, undo records and reports live |

## 1E.5 Folders that are not projects

A sweep never opens a subfolder, so every folder in Downloads that is not a project needs a decision.
There are three choices.

1. **Move it whole into a project.** A folder of photos from one cycling event belongs in a cycling
   photos project, as a unit. Add a rule to `config.json`:

   ```json
   "folder_rules": {"EventPhotos Download (123456789)": {"unit": "Cycling event photos"}}
   ```

   The folder moves, unopened, into the project's folder, and undo restores it like any other move.
2. **Sort its files one at a time.** An `attachments` folder that holds income papers, a police report
   and lease emails belongs in four different projects. A sweep does not do this, because a folder that
   mixes projects is where a person should read the plan. You do it once, as in Chapter 1D: assign the
   files with `assign_projects.py`, write a plan whose destinations climb out of the folder
   (`../Taxes/2021 W2.pdf`), check it with `apply_plan.py --check`, and apply it. Afterward, hash the
   files at their new locations and compare them with the snapshot. `verify.py` cannot confirm this
   kind of run, because it looks only inside the folder you gave it and reports the moved files as lost.
3. **Leave it.** Do nothing, and the sweep leaves the folder alone and counts it.

To find the folders that still need a decision:

```bash
python3 sweep.py folders
```

When it reports zero, every folder in Downloads is a project, moves as a unit, or has been sorted.

## 1E.6 Try it before you schedule it

Run a dry run. It does all the work except the moves:

```bash
python3 sweep.py run --dry-run
python3 sweep.py status
```

Then a real run, by hand, with new files in the folder:

```bash
python3 sweep.py run
```

If a sweep goes wrong, undo it. Each sweep keeps its own record, so you can undo the latest or any
earlier one:

```bash
python3 sweep.py undo                      # the latest sweep
python3 sweep.py undo 2026-10-17-093819-255   # a named one; `status` lists them
```

## 1E.7 The gates

With no person approving, the checks that a person would make are written into the code. A sweep stops,
with nothing moved, when any gate fails.

- It never overwrites a file. A name already taken gets `(2)`.
- It never deletes anything, and never opens a subfolder.
- More than `max_moves` moves means something unusual happened, so it moves none and says so.
- Files labeled credentials, or that the model cannot label, stay where they are, because a key file in
  the wrong folder is hard to find again.
- Files the model cannot place stay where they are.
- The undo record is written before the first move, and the plan must pass `apply_plan.py --check`.
- Afterward, every moved file is hashed again. One mismatch undoes the whole sweep.

The report holds counts, never file names, and so does the notification macOS shows.

What the gates cannot catch is a wrong filing. A sweep with a vague description will cheerfully put a
lease in Taxes. That is why section 1E.1 keeps a weekly look at the report as your job.

## 1E.8 Installing the schedule

On macOS, the system that runs jobs on a schedule is launchd. It reads a property list that names the
program and the times. The `agent` command writes one for you:

```bash
python3 sweep.py agent > ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
launchctl load ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

Run both in Terminal.app. Before that, run `python3 sweep.py run` once by hand and say yes if macOS asks
whether Terminal may access your files.

The job does not run on Sundays at 3 AM, as you might expect. It runs every day at 3 AM and at every
login, and passes `--if-due 7`, which makes the sweep do nothing unless a week has passed since the last
real one. Section 1E.9 explains why.

To prove that the scheduled job, not just your terminal, can read the folder, run a one-off copy of the
job through launchd. Use the interpreter path from the plist (`plutil -p` on the file shows it):

```bash
launchctl submit -l boringstuff.permtest \
  -o "$HOME/Library/Application Support/downloads-sweep/permtest.log" \
  -e "$HOME/Library/Application Support/downloads-sweep/permtest.log" \
  -- /path/to/python3 "$PWD/sweep.py" run --dry-run \
  --config "$HOME/Library/Application Support/downloads-sweep/config.json"
```

Wait ten seconds, read the log, then remove the test job with `launchctl remove boringstuff.permtest`.
"nothing new to sort" means launchd can read the folder. "no access to the folder" means macOS is
blocking it; grant your Python access in System Settings, under Privacy & Security. A submitted job
restarts itself, so the log may show its message twice.

To turn the schedule off:

```bash
launchctl unload ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

## 1E.9 What a laptop does to a schedule

A laptop is rarely awake at 3 AM, and each way it can be absent behaves differently.

**Asleep.** launchd runs a missed calendar job when the Mac wakes. This case needs nothing from you.

**Powered off.** launchd does not run a job it missed while the Mac was off, not even at the next
start. That is why the job also runs at login, and why `--if-due 7` exists: the login run catches up, and the
rule keeps every login from sweeping. A sweep that was skipped or stopped (no model, no permission) does
not count as the last sweep, so it tries again the next day.

**On battery.** The sweep loads a model, which takes several gigabytes of memory and a minute of processor
time. Plugged in, it always runs. On battery, it runs only at or above `min_battery_percent`. A skipped
run leaves no record, so the next check tries again.

**The model server is not running.** With `manage_model` on, the sweep starts it. If the LM Studio app is
closed, `lms server start` launches LM Studio in the background (you will see a process with
`--run-as-service` in its name), loads the model and runs the sweep. When it finishes, the sweep unloads
the model, stops the server, and ends the background process if it was the one that started it. The
process takes a few seconds to exit after the sweep returns, so a check made the instant it finishes may
still see it. If LM Studio was already open, the sweep leaves it open.

## 1E.10 What we tested

The tests in `test_sweep.py` run the whole sweep against a small fake model server, with no real model:
filing into existing folders and leaving everything else alone, undo, the dry run, the move limit, a
missing server, a second sweep with nothing new, folder rules, the weekly rule, the plist, and the
battery arithmetic. Sixteen tests run, and one skips itself on a plugged-in Mac, so a real low battery is
not exercised.

We also ran it for real. A sweep with a real model, gemma-4-e4b, on a practice folder laid out like an
organized Downloads put 56 of 59 files where the answer key puts them, and undo restored all 59. On a
real Downloads folder, launchd started the job with the LM Studio app quit, which brought up the
model server, filed two test files into Taxes and Workouts, held a fake key labeled credentials, shut the
server down, and left no model loaded. The test files were undone and removed afterward.

Not tested: the job running unattended at 3 AM for weeks. A schedule is only proven by the first few weeks
of reports.

## 1E.11 Limits

- A sweep files by description. When a description is vague, expect wrong filings; the fix is a better
  description, not a different model.
- The gates protect against floods, overwrites and sensitive labels. They do not know your intent.
- Only a Mac gets the scheduler as written. On Linux the same idea uses cron or systemd timers, and on
  Windows the Task Scheduler; the sweep itself is plain Python and runs anywhere, but nothing here has
  been tried on those systems.
- A job that changes your files while you are away has to be a job you can read back. Look at `status`
  weekly for the first month.

## Exercises

1. Run `python3 sweep.py run --dry-run` on a practice folder that has project folders and a few new loose
   files. What does the report say about files held and why?
2. Add a `folder_rules` entry for a folder of your own. Run a dry run, then a real run, then undo it.
3. Set `min_battery_percent` to 101, unplug your laptop, and run the sweep. Where does it say it skipped?
4. Write a description for two similar projects that does not let them overlap, run the sweep on files
   that could belong to either, and see where they land.
