# Chapter 1: what we tested

Back to the [chapter](README.md).

## Tested

`test_roundtrip.py` runs 16 tests on throwaway folders: plan, apply, verify, and undo, including the refusals (a skipped file, a
second apply while one is on record, undo twice, undo with a moved file gone or the original spot occupied, a plan marked with
the wrong mode). It also covers a Finder `.DS_Store` file inside a created folder, and a real file inside a created folder
that is never deleted. All 16 passed in 2.7 seconds on macOS, run for this page.

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
- Sonnet and Opus. The model table in section 1.5 is advice, not a measurement. Only the default model and Haiku produced plans.
- Whether two runs of the same model produce the same plan. Exercise 6 asks the reader to try.
- That a sorting plan is good. The verifier proves nothing was lost, not that the folders make sense.

## How much to trust it

The 16 tests are repeatable and prove the safety machinery; the model comparison and the real-folder runs are single runs, so treat them as anecdotes.
