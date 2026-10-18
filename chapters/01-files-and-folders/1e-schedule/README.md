# Chapter 1E: Keeping it sorted

Chapter 1D sorted a Downloads folder once, with a person approving the plan. The folder does not stay
sorted: new files arrive every day. This chapter sets up a weekly sweep that files only the new
arrivals into the project folders you already have, without you.

It is the first place in the book where an agent acts while nobody is watching, so most of the work is
in the limits placed on it and in how you undo it. [Chapter 7](../../../README.md#chapters), which is
planned and not yet written, will generalize scheduling to every chore in the book and cover the harder
cases this chapter only mentions.

## 1E.1 Why schedule it

A job is worth scheduling when it repeats, each run is small, and a mistake is cheap to reverse. A week of
downloads is a few dozen files and each sweep has its own undo. The sort in Chapter 1D does not fit that
description, which is why it stayed manual.

Some steps can run with nobody watching and some cannot. Assigning files to projects, building the plan,
and checking it change nothing, so they can run on a schedule and leave a plan for you to read later.
Moving files is the step a person should own. The agent that built Chapter 1D was stopped by the
permission system when it tried to move files in a real folder, even though the user had asked for it,
and that is the system working as designed. A sweep moves files without asking only because the
decision was made in advance and written in code: section 1E.6 lists the gates, and a sweep that fails
one moves nothing.

The same line holds if you schedule Claude Code instead of a script. Headless runs use `claude -p`, and
`.claude/settings.json` can allow exactly the scripts the job needs and nothing else, the same way this
repository denies `rm`. A job that is allowed to run `assign_projects.py` and `plan_projects.py` but not
`apply_plan.py` cannot apply by accident.

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
outside the repository, with one entry per project folder it found. If the folder holds a `Projects`
folder, which Chapter 1D makes unless you passed `--flat`, the entries come from the folders inside it
and sweeps file into those. Otherwise they come from the folders at the top. `init` detects the layout
rather than asking for 1D's `--flat`, so a folder sorted with 1D's defaults does not have to be sorted
again.

Every description says `EDIT ME`. Delete the entries that are not projects, merge any that overlap, and
write a real description for each of the rest, because the model files by those sentences. Say what
belongs and what does not:

> Mortgage refinancing paperwork: closing disclosures, wire instructions, appraisal reports and loan
> disclosures. Not the management, repairs or inspections of the rental house.

Two similar projects will split files at random unless each says what the other covers.

Settings you may want to change in `config.json`:

- `model` (default `google/gemma-4-e4b`): the model that reads the files, named the way your server
  names it.
- `base_url` (default `http://localhost:1234/v1`, LM Studio's server).
- `manage_model` (default `true`): the sweep starts LM Studio's server if it is not running, loads
  `model` under the name `sweep`, and afterward unloads that copy and stops only what it started. Models
  you loaded yourself stay loaded. Only LM Studio is managed. For Ollama, or an LM Studio server you run
  yourself, set it to `false` and keep the server running; the sweep then asks the server for `model` by
  name. For Ollama, `base_url` is `http://localhost:11434/v1` and `model` is a name from `ollama list`.
- `max_moves` (default 100): a sweep that would move more moves nothing.
- `hold_sensitivities` (default credentials and unknown): files with these labels never move.
- `min_age_minutes` (60) and `min_battery_percent` (50; 0 turns the check off).

## 1E.4 Folders that are not projects

A sweep never opens a subfolder, so each folder that is not a project needs a decision. Move it whole into
a project, with a rule in `config.json`:

```json
"folder_rules": {"EventPhotos Download (123456789)": {"unit": "Cycling photos"}}
```

Or sort its files one at a time, in a separate run that you approve, the way Chapter 1D does (an
`attachments` folder that mixes income papers, a police report, and lease emails is the case for it). Or
leave it. `python3 sweep.py folders` lists the ones still undecided; when it reports zero, every folder is
accounted for. A `Folders` folder made by Chapter 1D's `--top-level` sort is listed too, and leaving it is
the usual answer.

## 1E.5 Try it, then undo it

```bash
python3 sweep.py run --dry-run     # everything except the moves
python3 sweep.py run               # a real sweep
python3 sweep.py status            # the last sweeps, as counts
python3 sweep.py undo              # put the latest sweep back
```

To practice on a copy first, give it a config of its own with `init --config`, as the exercises do. Its
runs and its `projects.json` then stay beside that config, apart from the real ones, and every command
takes the same `--config`.

## 1E.6 The gates

With no person approving, the checks a person would make are in the code. A sweep that fails one moves
nothing. It never overwrites (a taken name gets `(2)`), never deletes, and never opens a subfolder. It
leaves files labeled credentials, files the model cannot label, and files the model cannot place.

It stops if it would move more than `max_moves` files. It also stops if the model answered none of the
files, so a server that refuses every request is reported, not counted as a quiet week. The plan must
pass `apply_plan.py --check`, and the undo record is written before the first move.

Afterward, every moved file is hashed again. One mismatch undoes the whole sweep. If that undo is itself
refused, the report says so and names the `sweep.py undo` command that finishes it. The report and the
notification hold counts, never names.

Some checks you might expect are not there. A sweep does not look for a backup. It holds only the labels
in `hold_sensitivities`, so a financial or health document moves like any other file unless you add
those labels. It hashes the moved files itself and does not run `verify.py`. An undone sweep does not
count toward `--if-due`, so the next daily check sweeps again; fix the description that caused the undo
first.

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
configured percentage, the sweep skips itself and tries again later. If the model server is not running
and `manage_model` is on, the sweep starts LM Studio's server and shuts down what it started.

The scheduled job does not run inside Terminal, so Terminal's permission does not cover it. macOS gives
the permission to the program that launchd, the macOS job scheduler, starts. That program is the Python
named in the plist (property list) file. Print the plist to see which one:

```bash
plutil -p ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

The first entry under `ProgramArguments` is that Python. To check that the job, not only your terminal,
can read the folder, run a one-off copy of it through launchd. Put that Python's path in place of
`/path/to/python3`:

```bash
launchctl submit -l boringstuff.permtest \
  -o "$HOME/Library/Application Support/downloads-sweep/permtest.log" \
  -e "$HOME/Library/Application Support/downloads-sweep/permtest.log" \
  -- /path/to/python3 "$PWD/sweep.py" run --dry-run \
  --config "$HOME/Library/Application Support/downloads-sweep/config.json"
```

Wait ten seconds, then read the log:

```bash
cat "$HOME/Library/Application Support/downloads-sweep/permtest.log"
```

Remove the test job:

```bash
launchctl remove boringstuff.permtest
```

"nothing new to sort" or "dry run" means launchd can read the folder. "no access to the folder" means
macOS is blocking it. Open System Settings, then Privacy & Security, then Full Disk Access, add the
Python that `plutil -p` showed, and run the test again. Grant it to that Python and not to Terminal as a
whole, since Full Disk Access lets everything the program launches read every file you own. A submitted
job restarts itself, so the log may show its message twice.

To turn the schedule off:

```bash
launchctl unload ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

## 1E.8 Limits

A sweep has not run unattended for weeks, so slow problems, such as a description that drifts out of date, are
unseen. Nothing here has been tried off a Mac. Look at `status` every week for the first month.

What we tested, and what we did not: [TESTED.md](TESTED.md).

## Common tasks

Run from `chapters/01-files-and-folders/1d-projects`.

| I want to... | Run | How often |
|---|---|---|
| Set up the sweep | `python3 sweep.py init ~/Downloads` | Once |
| Set up a practice sweep with its own runs | `python3 sweep.py init --config practice/config.json practice/downloads` | Before the real one |
| Preview a sweep | `python3 sweep.py run --dry-run` | Before the first real one |
| Run a sweep | `python3 sweep.py run` | On demand |
| See what happened | `python3 sweep.py status` | Weekly at first |
| Undo the latest sweep | `python3 sweep.py undo` | When one went wrong |
| Undo one particular sweep | `python3 sweep.py undo <run>` | When a sweep reports "undo refused" |
| List folders that need a decision | `python3 sweep.py folders` | After adding folders |
| See which Python the schedule runs | `plutil -p ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist` | Before granting Full Disk Access |
| Turn the schedule off | `launchctl unload ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist` | Rarely |

## Exercises

The exercises use Chapter 1D's practice fixture, with a config of its own so its runs stay apart from your
real sweeps. Build it from `chapters/01-files-and-folders/1d-projects`:

```bash
python3 make_project_mess.py practice/downloads
```

```bash
python3 sweep.py init --config practice/config.json practice/downloads
```

The fixture writes a `projects.json` with filled-in descriptions beside the folder, and `init` keeps it. Every
command below takes the same `--config practice/config.json`.

1. Dry-run the sweep with `python3 sweep.py run --dry-run --config practice/config.json`. The fixture
   has 59 loose files and no project folders yet. Read the report with `cat practice/runs/*/report.json`.
   What does it say about held files?
2. Make a subfolder that has sat for months, with `mkdir practice/downloads/race-photos` and then
   `touch -t 202605010900 practice/downloads/race-photos`. In `practice/config.json`, change
   `"folder_rules": {}` to `"folder_rules": {"race-photos": {"unit": "Marathon training"}}`. Dry-run,
   run, then undo with `python3 sweep.py undo --config practice/config.json`.
3. Rewrite the descriptions of Kitchen remodel and Insurance claim in `practice/projects.json` so they do
   not overlap. Dry-run again and compare `assignments.json` in the two newest folders under
   `practice/runs/`.
