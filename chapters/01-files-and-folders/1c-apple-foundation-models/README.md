# 1C: Private mode with Apple's on-device model (Mac only, nothing to download)

Same privacy design as [1B](../1b-local-model/README.md), but the local model is the
one already built into macOS. No LM Studio, no Ollama, no multi-gigabyte download, no
server to start.

## What you need

- A Mac with Apple Intelligence turned on, running **macOS 26 or later**
- Xcode or the Command Line Tools (for `swiftc`)
- For the Claude validation step: the standalone `claude` CLI, signed in

## Reading PDFs and images

Apple's on-device text model can't open a PDF or look at a picture. So a small helper,
[`extract_text.swift`](../extract_text.swift), pulls the text out first, using PDFKit and
Vision (OCR), both built into macOS: a PDF's text layer, OCR for scanned PDFs, and OCR plus
scene labels for images and screenshots. It's the same helper [1B](../1b-local-model/README.md)
uses. Build it once, **next to** `classify_apple`, which looks for it there:

```bash
swiftc -O extract_text.swift -o extract_text
```

Without it, PDFs and images are judged by filename only.

## Run it

From `chapters/01-files-and-folders/`:

```bash
python3 make_mess.py practice/downloads
python3 verify.py snapshot practice/downloads

swiftc -O extract_text.swift -o extract_text
swiftc -O 1c-apple-foundation-models/classify_apple.swift -o classify_apple
./classify_apple practice/downloads                              # on-device model reads the files
python3 make_plan.py practice/classification.json practice/downloads
python3 apply_plan.py --check practice/organize-plan.md practice/downloads
python3 validate_plan.py practice/claude-view.txt                # Claude sees metadata only
python3 apply_plan.py practice/organize-plan.md practice/downloads
python3 verify.py check practice/downloads
```

On our M4 Pro, all 28 files were labelled in about 18 seconds.

## Big folders: `--top-level`

For a folder with thousands of files in subfolders (a real Downloads), classify only the
loose files and let each subfolder move as one unit. See "Real folders: top-level mode" in
the [chapter README](../README.md).

```bash
./classify_apple practice/downloads --top-level
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

## How it differs from 1B

| | 1B (LM Studio / Ollama) | 1C (Apple Foundation Models) |
|---|---|---|
| Setup | Install an app, download a model, start a server | Nothing, if you're on macOS 26+ |
| Language | Python, over HTTP | Swift, calling a system framework |
| Model | Your choice, any size that fits | One fixed ~3B-class model |
| Keeps answers to the fixed lists via | JSON schema with enums | `@Generable` enums (guided generation) |
| Works on | Mac, Windows, Linux | Apple Intelligence Macs only |
| Context window | You set it | Small, so we classify one file at a time from its first 2 KB |

The two rows in the middle are the same idea in two runtimes: **constrain the output
type, not the prompt.** In Swift the enums *are* the schema:

```swift
@Generable enum Category { case documents, images, spreadsheets, ... }
@Generable struct Classification { var category: Category; var sensitivity: Sensitivity }
```

The model physically cannot answer outside them.

## Notes from building it

- **One session per file.** A `LanguageModelSession` keeps history, and the context
  window is small. A fresh session per file also keeps files from influencing each other.
- **Safety guardrails can refuse.** The on-device model has its own content filters, and
  they can throw on a file. The script catches that and leaves the file unlabelled, which
  `make_plan.py` treats as sensitive. A refusal can't turn into "looks harmless".
- **Don't run it while the Mac is busy.** On a real 60-file folder, our first run with PDF
  extraction failed on 31 files with a `SensitiveContentAnalysis` error, even on
  installers that had no extracted text. We had a 12B model running at the same time. Run
  alone, 59 of 60 worked. The script retries once and then fails closed, but the lesson is
  to check the *kind* of error before blaming the content.
- **One real refusal is normal.** The model's guardrail declined one file ("May contain
  sensitive content"). That file is treated as sensitive and sent to review, which is the
  right outcome.
- **Expect over-caution.** Told to prefer the sensitive label when unsure, this model
  flagged 51 of our 60 real files as sensitive. Safe, but it makes `_sensitive/` the biggest
  folder. Tighten the guidance in the `@Guide` text if that's too much for you.
- **`swiftc` on a single file just works.** No Xcode project, no Package.swift.
- Because it's a smaller model, expect some wrong labels. In our run it put a `.tar.gz`
  under Images and a to-do list under `legal`. That's what the metadata review step and
  your own read of the plan are for. See the [comparison in the chapter README](../README.md).

## Things worth poking at

- Run 1B and 1C on the same folder and diff the plans.
- Turn Apple Intelligence off in System Settings and run it. What does the error say?
- Add a file that mentions something the on-device model might refuse. Where does it end up?
