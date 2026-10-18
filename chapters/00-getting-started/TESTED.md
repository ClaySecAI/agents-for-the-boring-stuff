# Chapter 0: what we tested

Back to the [chapter](README.md).

This chapter and Chapter 0B (`setup.md`) explain ideas and walk through installs, so there is little to run. Chapter 0C
(`checking-claims.md`) uses checks from other chapters. Setup instructions refer to results in other chapters, such as the model
comparison in section 1D.12.

## Tested

- **Chapter 0B:** `check_setup.py` ran once, on a Mac with macOS 27.2. It reported Python, Claude Code, `lms`, `ollama`, and
  `swiftc` as ok, and reported no model server running. It changes nothing on the machine.
- **Chapter 0C:** `scripts/test_verify_editor_ledger.py` covers the ledger verifier (7 tests), and the quote and hash checks have
  their own tests in Chapters 1 and 9. The editor story in section 0C.1 comes from a real sequence of runs, recorded in
  [Chapter 10's source notes](../10-editor/source-notes.md): two runs that skipped the skill, one that stopped at line 431 of the
  catalog, one that skipped the catalog after its definition file changed, and one with the rules in the prompt whose ledger
  passed. That is five runs, not a measurement.

## Not tested

- The install steps in Chapter 0B on Windows or Linux. The text covers both, but we ran nothing there.
- The Windows and Linux branch of `check_setup.py` (the `pdftotext` and `tesseract` checks).
- The Ollama example in section 0B.7 (`classify_local.py` with `--base-url http://localhost:11434/v1`).
- The open-source PDF and image readers in section 0B.9, on any system.
- The model picks in the 0B.1 table for 8 GB and 16 GB machines. The book was written and tested on a 24 GB Mac.
- The setup steps from a fresh machine, as a reader new to the terminal would follow them.
- Whether the section 0.7 terms and the explanations in Chapter 0 are clear to a first-time reader.
- An agent trying to pass the ledger check in Chapter 0C without doing the work. One `grep` would do it; no run has tried.
- The sub-folder incident in section 0C.1: no record of that run is kept, in this file or in Chapter 1's.

## How much to trust it

One run of one script on one Mac, and five runs of one editor, are anecdotes; treat the setup steps for any other platform as untested.
