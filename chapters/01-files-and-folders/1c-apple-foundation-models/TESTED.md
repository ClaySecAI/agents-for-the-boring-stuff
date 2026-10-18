# Chapter 1C: what we tested

Back to the [chapter](README.md).

## Tested

- The whole pipeline in section 1C.3 ran on the 28-file practice folder on an M4 Pro. The on-device model labeled all 28 files in about 18 seconds. That is one timing, with no repeat count recorded.
- A 60-file test of real files (the chapter does not say whose or what kinds), two runs, with the Apple on-device model reading PDF text extracted by `extract_text`:
  - The first run failed on 31 of the 60 files with a `SensitiveContentAnalysis` error, including installers with no extracted text. A 12B model was running on the same Mac at the time.
  - The second run, with nothing else running, succeeded on 59 of the 60.
  - One file in the 60-file test was declined by the model's guardrails with "May contain sensitive content" and was sent to review. The chapter does not say which run that was.
  - The model flagged 51 of the 60 as sensitive, which made `_sensitive/` the largest folder.
- On the practice folder, two wrong labels were seen: a `.tar.gz` filed under Images and a to-do list filed under `legal`.

## Not tested

- Any Mac other than the M4 Pro, and any macOS version: the chapter requires macOS 26 or later and does not record which version the runs used.
- Run-to-run variation: the chapter gives one result per run described above, with no repeats.
- Whether the retry fixes a busy-Mac failure. The 59-of-60 result came from running the classifier alone, before the retry was added.
- Folders with thousands of files and the `--top-level` option: the chapter shows the command but reports no run of it.
- The exercises (Apple Intelligence turned off, a file the model refuses): the chapter reports no result for either.
- The Claude validation step (`validate_plan.py`) and the comparison with 1B appear in other chapters; this chapter reports no results for them.

## How much to trust it

Treat these as anecdotes from one author's Mac: the numbers show what happened once, not what you will see.
