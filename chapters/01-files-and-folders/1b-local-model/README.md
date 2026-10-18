# Chapter 1B: Keeping contents local with LM Studio or Ollama

[Chapter 1](../README.md) sends file contents to a cloud model. This variant keeps them on
your machine. A model running locally reads every file, and the cloud model sees only a table
of metadata: no names and no contents. The [who-sees-what table](../README.md#18-keeping-file-contents-on-your-machine)
in Chapter 1 shows each stage.

*Figure 1B.1: The private pipeline*

```
your files --> LOCAL model --> classification.json --> make_plan.py --> plan + claude-view.txt
 (contents)    (labels only)                           (no model)            |
                                                                             v
          apply_plan.py <-- you approve <-- validate_plan.py: Claude sees claude-view.txt only
```

## 1B.1 Requirements

- A local model server with one model downloaded: [LM Studio](https://lmstudio.ai) or [Ollama](https://ollama.com).
  [Chapter 0B](../../00-getting-started/setup.md) installs either one step by step; this chapter assumes you have finished
  section 0B.6 or 0B.7
- Python 3.9 or later; the scripts use only the standard library
- For the Claude validation step, the standalone `claude` command, signed in

Run `python3 chapters/00-getting-started/check_setup.py` to see which of these your computer has.

## 1B.2 Starting the model server

If you installed LM Studio in Chapter 0B, start its server and load a model:

*Listing 1B.1: Loading a model in LM Studio*

```bash
lms server start
lms load google/gemma-4-12b --identifier classifier --context-length 4096
```

Two details matter on a 24 GB Mac. First, cap the context length. The default asked for about
45 GB of memory and the load was refused. Classifying the first 2 KB of one file needs a few
thousand tokens of context, not 128,000. Second, the identifier `classifier` is the name
`classify_local.py` asks for by default.

Ollama serves the same API on a different port, under the model's own name instead of an identifier. If you installed Ollama instead, start it (`ollama serve`) and point the script at it:

```bash
python3 1b-local-model/classify_local.py <folder> --base-url http://localhost:11434/v1 --model <your-model>
```

## 1B.3 Reading PDFs and images

A plain-text reader sees a PDF or a screenshot as binary data, so without help the classifier
would judge those files by filename alone. On a Mac, a small helper fixes that using
frameworks that ship with macOS. Nothing is downloaded and nothing leaves the machine.

*Listing 1B.2: Building the extraction helper*

```bash
swiftc -O extract_text.swift -o extract_text     # run from chapters/01-files-and-folders/
```

`classify_local.py` finds `extract_text` on its own and uses it for PDFs and images:

- a PDF with a text layer is read directly (PDFKit)
- a scanned PDF has its first page rendered and read with on-device OCR (Vision)
- an image or screenshot gets OCR text plus a few scene labels, such as "document"

OCR is imperfect. In one test it read "240" as "249", so treat the output as a strong hint
and not a transcript. On other platforms, skip the helper or substitute your own extractor,
such as `pdftotext`, inside `read_head()`.

## 1B.4 Running the pipeline

From `chapters/01-files-and-folders/`:

*Listing 1B.3: From files to an approved plan*

```bash
python3 make_mess.py practice/downloads
python3 verify.py snapshot practice/downloads

python3 1b-local-model/classify_local.py practice/downloads     # the local model reads the files
python3 make_plan.py practice/classification.json practice/downloads
python3 apply_plan.py --check practice/organize-plan.md practice/downloads
```

Read `practice/organize-plan.md`. When you are satisfied, send the metadata to Claude, then
apply and verify:

*Listing 1B.4: The Claude gate, the move and the check*

```bash
python3 validate_plan.py practice/claude-view.txt   # Claude returns approve, or flags files to look at
python3 apply_plan.py practice/organize-plan.md practice/downloads
python3 verify.py check practice/downloads
```

For a folder with thousands of files in subfolders, classify only the loose files and let each
subfolder move as one unit. See [section 1.7](../README.md#17-folders-with-thousands-of-files).

```bash
python3 1b-local-model/classify_local.py practice/downloads --top-level
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

## 1B.5 How it works

The model cannot leak file contents because it has nowhere to write them. `classify_local.py`
asks the server for JSON that matches a schema in which `category` and `sensitivity` are
enums. The server's constrained decoding limits the model to the listed values. The `Why`
column in the plan holds label codes for the same reason.

The pass also does data-loss prevention. Each file receives a sensitivity label: `financial`,
`legal`, `government_id`, `health`, `credentials` or `personal`. `make_plan.py` routes labelled
files to `_sensitive/<kind>/`, where you can see them and later encrypt or exclude them.
Copies of a sensitive file stay inside that area. A file that cannot be labelled, or that
receives a value outside the lists, is treated as sensitive. The code fails closed.

Everything else is ordinary code: hashing, the plan table, the coverage check and the move.
The model only supplies labels.

## 1B.6 Two traps

### The model's log is a copy of your files

Nothing here leaves your machine, but your tools may keep what you send them. LM Studio writes
a server log, and ours held every prompt we sent, including text extracted from real files.
One day's log contained 155 prompts. Check before you call a run private:

```bash
ls ~/.lmstudio/server-logs/*/
grep -c "Content start" ~/.lmstudio/server-logs/*/*.log
```

Delete the logs from any run that touched sensitive files. Ask the same question of every tool
you add: where does it keep a copy of what I gave it?

### Reasoning models can spend the whole token budget

Our first run labelled 1 of 28 files. Gemma 4 is a reasoning model. It spent nearly all of the
200 output tokens thinking (197 of 200 in one probe) and returned an empty answer. Setting
`"reasoning_effort": "none"` in the request fixed it and cut a classification from about 15
seconds to about 4. For a lookup task, thinking is wasted effort.

When a model returns empty or truncated output, read the raw response before changing the
prompt.

## 1B.7 Choosing a model

A good local model fits in memory beside everything else you run, follows a JSON schema
reliably and reads documents well. We used `google/gemma-4-12b` (7.5 GB), a reasonable middle size
for a 24 GB laptop. A model of 20 billion parameters or more needs about 16 GB for itself and did not
load beside everything else on that machine, so we did not use one. Try two and compare their plans,
using the method from
[section 1.5](../README.md#15-choosing-a-model-for-the-job). Model names change quickly, so
check what is current.

## Common tasks

Run from `chapters/01-files-and-folders`.

| I want to... | Run | How often |
|---|---|---|
| Classify with LM Studio | `python3 1b-local-model/classify_local.py <folder>` | Each folder |
| Classify with Ollama | `python3 1b-local-model/classify_local.py <folder> --base-url http://localhost:11434/v1 --model <name>` | Each folder |
| Build the plan | `python3 make_plan.py practice/classification.json <folder>` | After classifying |
| Have Claude check the plan (metadata only) | `python3 validate_plan.py practice/claude-view.txt` | Before applying |
| Let it read PDFs and images (Mac) | `swiftc -O extract_text.swift -o extract_text` | Once |
| Free the memory when done | `lms unload --all` | After each session |

## Exercises

1. Swap the model and compare the plans. Where do a small and a large model disagree?
2. Add a file containing a made-up social security number. Does it land in
   `_sensitive/government_id/`?
3. Stop the LM Studio server partway through a run. What happens to the files that were not
   labelled?
4. Read `practice/claude-view.txt`. Could you work out what any file is from that alone?
