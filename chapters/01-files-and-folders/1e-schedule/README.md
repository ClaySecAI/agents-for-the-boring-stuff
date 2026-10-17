# Chapter 1E: Keeping it sorted

Chapter 1D sorted a Downloads folder once, with a person approving the plan. The folder does not stay
sorted: new files arrive every day. This chapter sets up a weekly sweep that files only the new
arrivals into the project folders you already have, without you.

It is the first place in the book where an agent acts while nobody is watching, so most of the work is
in the limits placed on it and in how you undo it. [Chapter 7](../../../README.md#chapters) generalizes
scheduling to every chore in the book, and covers the harder cases this chapter only mentions.

## 1E.1 Why schedule it

A job is worth scheduling when it repeats, each run is small, and a mistake is cheap to reverse. A week of
downloads is a few dozen files and each sweep has its own undo. The sort in Chapter 1D does not fit that
description, which is why it stayed manual.

## 1E.2 What a sweep does

A sweep looks only at loose files sitting directly in the folder. A local model reads each one that is
ready and picks one of your projects, and the file moves into that project's existing folder. Everything
else stays: subfolders, hidden files, files still downloading, files the model cannot place. A file is ready
when it is not hidden, is on disk, is not empty, is not a partial download, and has sat untouched for an
hour. Nothing leaves your machine, and Claude is not involved.

## 1E.3 Setting it up

You need a sorted folder ([Chapter 1D](../1d-projects/README.md)), a local model server
([Chapter 0B](../../00-getting-started/setup.md)), and a backup. For iCloud Drive or another protected
folder, read [section 1D.13](../1d-projects/README.md#1d13-protected-and-synced-folders) first. Commands run
from `chapters/01-files-and-folders/1d-projects`.

```bash
python3 sweep.py init ~/Downloads
```

This writes `config.json` and a starting `projects.json` to `~/Library/Application Support/downloads-sweep/`,
outside the repository, with one entry per folder it found. Every description says `EDIT ME`. Delete the
entries that are not projects, merge any that overlap, and write a real description for each of the rest,
because the model files by those sentences. Say what belongs and what does not:

> Mortgage refinancing paperwork: closing disclosures, wire instructions, appraisal reports and loan
> disclosures. Not the management, repairs or inspections of the rental house.

Two similar projects will split files at random unless each says what the other covers. Settings you may
want to change in `config.json`: `max_moves` (default 100; a sweep that would move more moves nothing),
`hold_sensitivities` (default credentials and unknown; files with these labels never move),
`min_age_minutes` (60), and `min_battery_percent` (50; 0 turns the check off).

## 1E.4 Folders that are not projects

A sweep never opens a subfolder, so each folder that is not a project needs a decision. Move it whole into
a project, with a rule in `config.json`:

```json
"folder_rules": {"EventPhotos Download (123456789)": {"unit": "Cycling photos"}}
```

Or sort its files one at a time, in a separate run that you approve, the way Chapter 1D does (an
`attachments` folder that mixes income papers, a police report and lease emails is the case for it). Or
leave it. `python3 sweep.py folders` lists the ones still undecided; when it reports zero, every folder is
accounted for.

## 1E.5 Try it, then undo it

```bash
python3 sweep.py run --dry-run     # everything except the moves
python3 sweep.py run               # a real sweep
python3 sweep.py status            # the last sweeps, as counts
python3 sweep.py undo              # put the latest sweep back
```

## 1E.6 The gates

With no person approving, the checks a person would make are in the code. A sweep that fails one moves
nothing. It never overwrites (a taken name gets `(2)`), never deletes, and never opens a subfolder. It
stops if it would move more than `max_moves` files. It leaves files labeled credentials, files the model
cannot label, and files the model cannot place. The undo record is written before the first move, the plan
must pass `apply_plan.py --check`, and afterward every moved file is hashed again. One mismatch undoes the
whole sweep. The report and the notification hold counts, never names.

A gate cannot catch a wrong filing. A vague description will put a lease in Taxes. So read the weekly
report, and fix the description.

## 1E.7 Installing the schedule

```bash
python3 sweep.py agent > ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
launchctl load ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

Run both in Terminal.app, after one manual `python3 sweep.py run` has let macOS ask whether Terminal may
reach your files. The job runs every day at 3 AM and at every login, and `--if-due 7` limits it to one real
sweep a week. The reason is the laptop: a Mac that was asleep runs a missed job when it wakes, but a Mac
that was off does not run one at the next start. The login run catches that case. On battery below the
configured percentage, the sweep skips itself and tries again later. If the model server is not running,
the sweep starts it and shuts down what it started.

To check that the scheduled job, not only your terminal, can read the folder, run a one-off copy through
launchd with `launchctl submit` and `--dry-run`; Chapter 7 shows the command and what each result means.
To turn the schedule off:

```bash
launchctl unload ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

## 1E.8 Limits

We tested the sweep with a fake model in `test_sweep.py`, with a real model on a practice folder (56 of 59
files in the right place, undo restoring all 59), and through launchd on a real Downloads folder. We have
not watched it run unattended for weeks, and nothing here has been tried off a Mac. Look at `status` every
week for the first month.

## Exercises

1. Dry-run the sweep on a practice folder that has project folders and a few new loose files. What does the
   report say about held files?
2. Add a `folder_rules` entry for a folder of your own, dry-run, run, then undo.
3. Write descriptions for two similar projects so they do not overlap, then sweep files that could belong
   to either.
