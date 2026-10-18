# Chapter 1E: what we tested

Back to the [chapter](README.md).

**Tested**

- `test_sweep.py` (in `chapters/01-files-and-folders/1d-projects`) runs 16 tests against a fake model server, and all 16 pass. They cover
  which files a sweep may touch, holding sensitive and unplaceable files, never overwriting a file, the power rules and a low battery,
  filing new loose files and leaving everything else, undo, a dry run moving nothing, too many moves stopping the sweep, a missing model
  server, a second sweep doing nothing, folder rules and their undo, listing untracked folders, the scheduler file (daily and at login,
  sweeping weekly), and `--if-due`.
- A real model on a practice folder: 56 of 59 files in the right place, and undo restoring all 59.
- The sweep through launchd on a real Downloads folder.

**Not tested**

- Unattended runs over weeks. We have not watched a scheduled sweep run on its own for that long.
- Any system other than a Mac.
- Repeat runs. We report one practice-folder result and one launchd result, and we did not record which model was used or what happened to
  the 3 misplaced files.

**How much to trust it**

The fake-model tests show the gates behave as written, but the real-model and launchd results are reported once each, so treat them as anecdotes
and read `status` every week for the first month.
