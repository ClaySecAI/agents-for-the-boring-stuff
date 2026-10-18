# Chapter 0: what we tested

Back to the [chapter](README.md).

This chapter and Chapter 0B (`setup.md`) explain ideas and walk through installs, so there is little to run. Setup instructions
refer to results in other chapters, such as the model comparison in section 1D.12.

## Tested

`check_setup.py` ran once, on a Mac with macOS 27.2. It reported Python, Claude Code, `lms`, `ollama`, and `swiftc` as ok, and
reported no model server running. It changes nothing on the machine.

## Not tested

- The install steps in Chapter 0B on Windows or Linux. The text covers both, but we ran nothing there.
- The Windows and Linux branch of `check_setup.py` (the `pdftotext` and `tesseract` checks).
- The model picks in the 0B.1 table for 8 GB and 16 GB machines. The book was written and tested on a 24 GB Mac.
- The setup steps from a fresh machine, as a reader who has never used a terminal would follow them.
- Whether the section 0.7 terms and the explanations in Chapter 0 are clear to a first-time reader.

## How much to trust it

One run of one script on one Mac is an anecdote; treat the setup steps for any other platform as untested.
