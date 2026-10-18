# Chapter 1E: what we tested

Back to the [chapter](README.md).

**Tested**

- `test_sweep.py` (in `chapters/01-files-and-folders/1d-projects`) runs 26 tests against a fake model server and a fake `lms` command.
  On our last run, on Python 3.9 and on a current Python, 25 passed and one skipped: the low-battery test runs only when the Mac reports
  battery power and skips otherwise. That run skipped it, so it checked the power rules but not the skip itself. The tests cover which files a sweep
  may touch, holding sensitive and unplaceable files, never overwriting a file, the power rules, filing new loose files and leaving
  everything else, undo, a dry run moving nothing, too many moves stopping the sweep, a missing model server, a second sweep doing
  nothing, folder rules and their undo, listing untracked folders, the scheduler file (daily and at login, sweeping weekly), and
  `--if-due`. Since October 2026 they also cover asking the server for the configured model, loading and unloading only the sweep's own
  copy of it, stopping when the model answers no file, a `|` in a file name, a practice config keeping its runs apart, a folder sorted
  into `Projects/`, an undone sweep not counting toward `--if-due`, and a failed check whose undo is refused.
- A real model on a practice folder: 56 of 59 files in the right place, and undo restoring all 59.
- The sweep through launchd on a real Downloads folder.

**Not tested**

- Unattended runs over weeks. We have not watched a scheduled sweep run on its own for that long.
- Any system other than a Mac.
- Repeat runs. We report one practice-folder result and one launchd result, and we did not record which model was used or what happened to
  the 3 misplaced files.
- The October 2026 fixes against real servers. The practice-folder and launchd results come from the code before the fixes to the model
  name, the unload, and the `Projects/` layout. Since then the sweep has run only against the fake server and the fake `lms`, not against
  LM Studio or Ollama.

**How much to trust it**

The fake-model tests show the gates behave as written, but the real-model and launchd results are reported once each, so treat them as anecdotes
and read `status` every week for the first month.
