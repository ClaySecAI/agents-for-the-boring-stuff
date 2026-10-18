# Chapter 1D: what we tested

Back to the [chapter](README.md).

## Tested

Unit tests, no model: `test_projects.py` runs 52 tests and `test_sweep.py` runs 26; both passed when we last ran them, with the sweep's
low-battery test skipped (it runs only on battery power). They use a fake model server, so they check our code, not any model's judgment. They
cover:

- planning, the Also column, empty files, protect-list ranking, and the check that Claude's view has no file names
- a `|` in a file name, through planning, apply, tags and undo
- `--top-level`, `--keep-folders`, and `--flat`, including apply and undo
- Finder tags: add, keep existing tags, remove
- the closed answer set, bad project names, and hidden signals
- linking by shared account number, including conflicts
- rules learned from corrections, and the rename helpers
- the `pdftotext` fallback, the Apple helper, and the scorer
- the sweep: files moved and undone, dry runs, the move limit, a missing model server, the launchd plist, and the weekly schedule check
  ([Chapter 1E's TESTED.md](../1e-schedule/TESTED.md) lists the rest)

Model runs on the practice fixture (59 invented files, eight invented projects, plus an answer key). These are single runs.

- Section 1D.3, Table 1D.1: who wrote the project list. You (8 groups, 100% cluster purity, 8 of 8 projects), the model told to think in
  projects (10 groups, 88%, 7 of 8), the model with no steer (10 groups, 92%, 7 of 8). Sorting by extension, best case, 44%.
- Section 1D.7, Table 1D.2: Gemma 4 12B in LM Studio on the readable fixture and a `--blind` fixture. Six runs: 56 and 50 (name and
  contents), 50 (plus date, blind only), 55 (plus website, blind only), 59 and 55 (website and date). Every wrong answer was an
  `Unsorted` file; none went to a wrong project.
- Section 1D.7, Table 1D.3: `--hold-out`, four runs. Marathon training left off: 59 of 59 under both prompt rules. Insurance
  claim left off: 54 of 59 with the original rule (5 filed under a wrong project), 56 of 59 with the stricter rule (3).
- Section 1D.7, `--statements`: 62 files. 60 right with the per-file pass alone, 62 after `link_files.py`.
- Section 1D.7: Claude's review of the blind-run plan (all signals), one run. It approved a plan in which four files that belonged
  to projects sat in `Unsorted`.
- Section 1D.12, `bakeoff.py`: 11 models on three 59-file fixtures (readable, blind, hold-out). The README reports one score per cell.
  Wrong-project totals range from 1 (gemma-4-e4b) to 24 (llama3.2 3B) among the language models, and 10 to 14 among the embedding
  models. The models are 3 to 14B language models (LM Studio and Ollama), Apple's on-device model, and three embedding models.

A real folder: section 1D.13 sorted an iCloud Downloads folder of 411 files. The README reports
what went wrong, not a score: 222 files were cloud-only, and macOS blocked Python started from the Claude app's terminal panel
while Terminal.app could read the folder. A bicycle-manual misfiling on a real folder is mentioned in 1D.7.

## Not tested

- A score on the real folder: the README gives no accuracy number for the 411-file run.
- Any system but macOS: the README describes the `pdftotext` and `tesseract` fallback and says Finder tags do nothing on other
  systems. The unit tests exercise the `pdftotext` fallback with a stub. It names no real run on Linux or Windows, and it reports no
  `tesseract` run.
- The scheduled job: Chapter 1E covers it, and [its TESTED.md](../1e-schedule/TESTED.md) records one sweep through launchd on a real
  Downloads folder. No scheduled run of assigning and planning on their own is reported.
- Repeat runs: each model-run cell is one run. Exercise 4 asks you to repeat `suggest_projects.py`; we report no variation across
  runs.
- Other models in the 1D.7 tables: tables 1D.2 and 1D.3 are Gemma 4 12B only. The date signal might matter for another model;
  the README says we did not tell the two explanations apart.
- How often real folders contain groups that link: the `--statements` fixture was built to match the problem we saw.
- Rules on a messy folder: the rule tests use a fixture whose statements share a website and an account number.
- Hardware, model versions, and LM Studio or Ollama versions: the README says only "one machine, one afternoon".

## How much to trust it

The code is covered by 78 tests that pass or skip as described above, but every model number is a single run on a clean, invented 59-file folder, so read the
tables as an illustration of the method and not as a ranking.
