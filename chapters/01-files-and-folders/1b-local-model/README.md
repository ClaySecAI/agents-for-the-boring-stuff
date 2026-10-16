# 1B: Private mode with a local model (LM Studio or Ollama)

Chapter 1 sends file contents to a cloud model. This variant keeps them on your
machine: a model running locally reads every file, and the cloud model only ever sees
a **metadata table**, never names or contents. See [the chapter README](../README.md)
for the full "who sees what" table.

```
your files --> LOCAL model --> classification.json --> make_plan.py --> plan + claude-view.txt
 (contents)    (labels only)                           (no model)            |
                                                                             v
          apply_plan.py <-- you approve <-- validate_plan.py: Claude sees claude-view.txt only
```

## What you need

- [LM Studio](https://lmstudio.ai) or [Ollama](https://ollama.com), with one model downloaded
- Python 3.9+ (standard library only, no pip install)
- For the Claude validation step: the standalone `claude` CLI, signed in

## Setup (LM Studio)

```bash
lms server start
lms load google/gemma-4-12b --identifier classifier --context-length 4096
```

Two details that matter on a 24 GB Mac:

- **Cap the context length.** The default asked for ~45 GB of memory and refused to load.
  Classifying one file's first 2 KB needs a few thousand tokens, not 128k.
- **The identifier `classifier`** is what the script asks for by default.

**Ollama instead?** It serves the same API on a different port:

```bash
python3 classify_local.py <folder> --base-url http://localhost:11434/v1 --model <your-model>
```

## Reading PDFs and images (macOS, recommended)

Without help, the classifier can only read plain text. A PDF or screenshot is a
binary file to it, so it would be judged by filename alone. On a Mac you can fix that with
one small helper that uses frameworks already built into macOS (no download, nothing
leaves your machine):

```bash
swiftc -O extract_text.swift -o extract_text     # run from chapters/01-files-and-folders/
```

`classify_local.py` finds `extract_text` automatically and uses it for PDFs and images:

- **PDF with text:** reads its text layer (PDFKit).
- **Scanned PDF:** renders the first page and reads it with on-device OCR (Vision).
- **Image or screenshot:** on-device OCR, plus a few scene labels like "document".

OCR isn't perfect (in our test it read "240" as "249"), so treat the result as a strong
hint, not a transcript. Not on a Mac? Skip the helper, or swap in your own extractor
such as `pdftotext` at the same spot in `read_head()`.

## Run it

From `chapters/01-files-and-folders/`:

```bash
python3 make_mess.py practice/downloads
python3 verify.py snapshot practice/downloads

python3 1b-local-model/classify_local.py practice/downloads     # local model reads the files
python3 make_plan.py practice/classification.json practice/downloads
python3 apply_plan.py --check practice/organize-plan.md practice/downloads
```

Read `practice/organize-plan.md`. Then the Claude gate and the move:

```bash
python3 validate_plan.py practice/claude-view.txt     # Claude: approve, or flag files to look at
python3 apply_plan.py practice/organize-plan.md practice/downloads
python3 verify.py check practice/downloads
```

## Gotcha: "local" doesn't mean "leaves no trace"

Nothing here leaves your machine, but your tools may still *keep* what you send them.
LM Studio writes a server log, and ours held every prompt we sent, including the text pulled
from real files (155 prompts in one day's log). Check before you call a run private:

```bash
ls ~/.lmstudio/server-logs/*/            # one log per day
grep -c "Content start" ~/.lmstudio/server-logs/*/*.log
```

Delete the logs of any run that touched sensitive files, and treat the same question as
standing advice for any tool you add: where does it keep a copy of what I gave it?

## Big folders: `--top-level`

For a folder with thousands of files in subfolders (a real Downloads), classify only the
loose files and let each subfolder move as one unit. See "Real folders: top-level mode" in
the [chapter README](../README.md).

```bash
python3 1b-local-model/classify_local.py practice/downloads --top-level
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

## How it works

**The model can't leak because it can't write prose.** `classify_local.py` asks the
server for JSON that matches a schema where `category` and `sensitivity` are
**enums**. The server's constrained decoding means the model can only pick from the
lists. There's no free-text field for file contents to slip through. The `Why`
column in the plan holds label codes only, for the same reason.

**It's a DLP pass, not just a sorter.** Each file also gets a sensitivity label
(`financial`, `legal`, `government_id`, `health`, `credentials`, `personal`).
`make_plan.py` routes those to `_sensitive/<kind>/` so you can see (and, later,
encrypt or exclude) them. Copies of a sensitive file stay inside the sensitive area
too. If a file can't be labelled, or the model says something outside the lists,
it **fails closed**: the file is treated as sensitive, never as harmless.

**Duplicates, coverage and moves are plain code.** Hashing, the plan table,
`--check` and the move are all deterministic. The model only supplies labels.

## Gotcha: reasoning models eat your token budget

Our first run labelled **1 of 28** files. Gemma 4 is a reasoning model. It spent
nearly all 200 output tokens "thinking" (197 of 200 in one probe) and returned an
empty answer. The fix is one line in the request, `"reasoning_effort": "none"`,
which cut a classification from about 15 s to about 4 s. For a lookup task like this,
thinking is wasted. Lesson: **when a model gives empty or truncated output, look at the
raw response before blaming the prompt.**

## Choosing the model

The right local model is one that fits in memory next to everything else you run, follows
a JSON schema reliably, and reads documents well. We used `google/gemma-4-12b` (7.5 GB).
It was already installed, and it's a sensible middle size for 24 GB. Larger models
(like a 27B at 4-bit, ~16 GB) may read ambiguous files better but leave little room for
the rest of your system. Try two and compare the plans. Same method as the Haiku test in
the [chapter README](../README.md). Model names change quickly, so check what's current.

## Things worth poking at

- Swap the model and diff the plans. Where do small and large models disagree?
- Put a file with a fake SSN in the folder. Does it land in `_sensitive/government_id/`?
- Stop the LM Studio server mid-run. What happens to the files it didn't label?
- Read `practice/claude-view.txt`. Could you work out what any file is from that alone?
