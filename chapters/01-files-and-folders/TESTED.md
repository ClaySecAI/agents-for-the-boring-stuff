# Chapter 1: what we tested

Back to the [chapter](README.md).

## Tested

`test_roundtrip.py` runs 35 tests on throwaway folders: plan, apply, verify, and undo, including the refusals (a skipped file, a
second apply while one is on record, undo twice, undo with a moved file gone or the original spot occupied, a plan marked with
the wrong mode). It also covers a Finder `.DS_Store` file inside a created folder, and a real file inside a created folder
that is never deleted.

Nineteen of the 35 were added on 2026-10-18, after a review found ways the safety promises broke. Each one failed on the old
scripts and passes now. They cover two files whose names differ only in capital letters, plan paths that leave the folder, a
`To` that another row uses as a folder, a folder that existed before apply (undo now keeps it), links, a folder given as `.`, an
apply that stops at its first move or partway through, a move whose `To` was taken after the check, and `--help`. All 35 passed
on macOS in 5.1 seconds with Python 3.15 and in 12.6 seconds with the Mac's own Python 3.9.6, run for this page.

The planning step ran on the 28-file practice folder with the session's default model and again with `model: haiku`, one run
each (section 1.5). The default model's plan covered 28 of 28 files. Haiku's covered 26 of 28 and skipped `old_stuff/`. The coverage
check rejected Haiku's plan and listed the two skipped files. The verifier passed anyway, because nothing had moved.

Top-level mode was used on one real Downloads folder of well over 100,000 files (section 1.7).

The validator's boundary was tested once. With only `--tools ""`, the model could still see the account's connectors. After
adding `--strict-mcp-config` with an empty server list, they were gone (section 1.8).

The two private pipelines (1B and 1C) ran once each on the fixture (28 files) and once on a 60-file slice of a real Downloads
folder (section 1.9).

## Not tested

- Windows and Linux. The tests ran on macOS only, and the Finder `.DS_Store` handling is Mac-specific.
- A disk that tells `A.txt` and `a.txt` apart. The tests ran on the Mac's default disk, which treats them as one name.
- Sonnet and Opus. The model table in section 1.5 is advice, not a measurement. Only the default model and Haiku produced plans.
- Whether two runs of the same model produce the same plan. Exercise 6 asks the reader to try.
- That a sorting plan is good. The verifier proves nothing was lost, not that the folders make sense.

## How much to trust it

The 35 tests are repeatable and prove the safety machinery; the model comparison and the real-folder runs are single runs, so treat them as anecdotes.
