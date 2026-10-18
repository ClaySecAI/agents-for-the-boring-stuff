# Chapter 1B: what we tested

Back to the [chapter](README.md).

## Tested

- **Model and machine:** `google/gemma-4-12b` (7.5 GB) in LM Studio on a 24 GB Mac. The default context length asked for about 45 GB and the load was refused; with `--context-length 4096` it loaded.
- **First run:** 1 of 28 files was labeled, because Gemma 4 spent 197 of 200 output tokens on reasoning in one probe and returned an empty answer. With `"reasoning_effort": "none"` set, one classification dropped from about 15 seconds to about 4.
- **OCR:** on-device OCR read "240" as "249" in one test.
- **Server log:** one day's LM Studio log held 155 prompts, including text extracted from real files.
- **Model size:** a model of 20 billion parameters or more did not load beside everything else on that machine, so we did not use one.

The chapter folder has no test file of its own. We re-ran no command for this record, so these numbers come from the author's earlier runs as the chapter reports them.

## Not tested

The author must fill these in. Each line is a gap in what the chapter records, not a statement that it was or was not tried.

- The Ollama path (`--base-url http://localhost:11434/v1`): no run is recorded.
- The `pdftotext` alternative for PDFs: no run is recorded.
- Any platform other than a Mac, including the non-Mac fallback in section 1B.3.
- Any model other than Gemma 4 12B, and any Mac with more or less than 24 GB.
- The `--top-level` option for large folders.
- The Claude validation step (`validate_plan.py`) as part of a 1B run.
- Whether the Swift helper reads every PDF and image type.

## How much to trust it

Each figure here is a single observation on one machine with one model, so treat it as an anecdote and re-measure before relying on it.
