---
name: organize-by-project
description: Sort a folder into project folders using a local model, a human-written project list, and an approved plan. Use for requests like "group my Downloads by what the files are for" when contents may be sensitive.
---

# Organize a folder by project

Paths below are relative to `chapters/01-files-and-folders/1d-projects/` (call it `$P`) and its parent (`$C`).
Input: the folder, and a project list. Ask for both if missing. Back-up status: ask whether the folder is
backed up before the first apply. Work on a copy when the user has any doubt.

## 1. Check the local model is up

`curl -s localhost:1234/v1/models` (LM Studio) or `localhost:11434/v1/models` (Ollama). If neither answers,
tell the user to start one. Do not fall back to a cloud model: the point is that file contents stay here.

## 2. Assign (the local model reads the files)

`python3 $P/assign_projects.py <folder> <projects.json> [--top-level]` writes `assignments.json`.
Report how many files were placed, left unsorted or failed. Do not print file names or contents.

## 3. Optional improvements, each only if the user wants it

- Learned rules: `python3 $P/rules.py apply <folder> assignments.json rules.json` (rules come from
  `teach.py` corrections, `rules.py learn`).
- Better names: `python3 $P/suggest_names.py <folder>` then pass `--names names.json` in step 4.

## 4. Build the plan

`python3 $P/plan_projects.py assignments.json projects.json <folder> [--top-level --keep-folders] [--flat] [--names names.json]`

Ask the user before choosing `--flat` or the nested `Projects/` layout. They own the layout.
`--keep-folders` leaves subfolders alone and is the safe start on a real folder.

## 5. Check, then ask

1. Snapshot before anything moves: `python3 $C/verify.py snapshot <folder>`.
2. Coverage and conflicts: `python3 $C/apply_plan.py --check organize-plan.md <folder>`. It rejects a plan that
   skips items or collides on a destination.
3. Optional second opinion that sees no names or contents: `python3 $C/validate_plan.py claude-view.txt --prompt $P/validator-prompt-projects.md`.
4. Tell the user the counts per project id (P1, P2...), how many are unsorted or empty, and the plan's totals,
   from script output. Do not open `protect-list.txt`: tell the user it ranks the projects and to read it themselves.
5. STOP. Apply only after an explicit yes.

## 6. Apply, verify, tag

`python3 $C/apply_plan.py organize-plan.md <folder>`, then `python3 $C/verify.py check <folder>`, then
`python3 $P/tag_files.py organize-plan.md <folder>` for Finder tags (macOS). Undo is
`python3 $C/undo_plan.py <folder>`; tell the user it exists, and that `tag_files.py --remove` clears tags.

Report: files moved per project id, unsorted count, and how to undo. Name no project and no file.
