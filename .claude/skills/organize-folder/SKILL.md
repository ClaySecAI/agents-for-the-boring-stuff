---
name: organize-folder
description: Tidy a messy folder using a propose, approve, apply, verify workflow. Use when asked to organize, sort, clean up, or declutter a directory.
---

# Organize a folder

Input: the path to one folder. If the user hasn't given one, ask. Do not guess.

## 1. Inspect (read-only)

- Count first: `find <folder> -type f | wc -l`. If the folder holds thousands of files
  (extracted archives, `node_modules`, cloned projects), do NOT plan every file. Use
  **top-level mode**: only the folder's direct children are items, and each subfolder is
  moved as one unit and never opened. Write `Mode: top-level` in the plan (see step 2).
- Otherwise, list everything in the folder (top level and subfolders).
- Look beyond file extensions. For small text-like files, read the first few
  lines to learn what they are. A file called `scan_0042.pdf` may be a receipt
  or a lease.
- Find exact duplicates by comparing content hashes (`shasum -a 256`), not names.

## 2. Propose

Write the plan to `organize-plan.md` **next to the target folder, not inside it**.
Use this format:

```
# Plan for <folder>

Mode: top-level          <- only when using top-level mode; omit the line otherwise

Categories used: <list, with one line on why each exists>

| From | To | Why |
|---|---|---|
| IMG_2041.jpg | Photos/IMG_2041.jpg | image file |
| notes.txt | _needs-review/notes.txt | could be work or personal |

Duplicates: <which files are identical, which one stays in place>
Renames: <none, or list with reasons>
```

In top-level mode a subfolder is one row (for example `my-project | Folders/my-project`).
A row whose From equals its To means "leave it where it is".

Prefer a small number of obvious categories (for example Documents, Images,
Spreadsheets, Installers, Archives, Text) over many clever ones. Fewer
folders are easier to trust.

## 3. Check, then stop for approval

First validate your own plan:
`python3 chapters/01-files-and-folders/apply_plan.py --check <plan> <folder>`.
It rejects a plan that skips files (including ones in subfolders), collides on
destinations (names that differ only in upper and lower case collide too), moves a link,
points outside the folder, or names files that don't exist. Fix the plan and re-check
until it passes. Never ask for approval on a plan that fails the check. If it reports an
earlier applied plan still on record, tell the user and ask whether to undo it first.

Then show the user a short summary of the plan and ask them to approve or edit it.
Do not move anything yet. Wait for a clear yes.

## 4. Apply

Execute exactly what the approved plan says by running
`python3 chapters/01-files-and-folders/apply_plan.py <plan> <folder>`, which performs the
plan's table and nothing else. If the script isn't available, or it stops with an error,
stop and ask. Do not move files by hand: that skips every check, and `mv` overwrites an
existing file without asking. If the script says it was interrupted, show the user the
undo command it printed. Do nothing the plan didn't list. Stop and ask if anything else
unexpected comes up.

## 5. Report and verify

Summarize what moved. Remind the user to run the verifier from the chapter
README, which independently confirms no file was lost or changed. Also tell them the
move can be reversed: `apply_plan.py` saved a record, and
`python3 chapters/01-files-and-folders/undo_plan.py <folder>` puts everything back.
