# Chapter 1C: Keeping contents local with Apple's on-device model

This chapter uses the same privacy design as [Chapter 1B](../1b-local-model/README.md). The
local model is the one already built into macOS, so there is no app to install, no model to
download, and no server to start.

## 1C.1 Requirements

- A Mac with Apple Intelligence turned on, running macOS 26 or later (turn it on in System Settings, then
  Apple Intelligence & Siri; [section 0B.8](../../00-getting-started/setup.md#0b8-a-local-model-option-3-apples-on-device-model)
  walks through it)
- Xcode or the Command Line Tools, for `swiftc`. If `swiftc --version` prints an error, run
  `xcode-select --install` and wait for it to finish
- For the Claude validation step, the standalone `claude` command, signed in

## 1C.2 Reading PDFs and images

Apple's on-device model works on text. It cannot open a PDF or look at a picture. A small
helper, [`extract_text.swift`](../extract_text.swift), extracts the text first, using PDFKit and
Vision (OCR), both part of macOS. It reads a PDF's text layer, applies OCR to scanned PDFs, and
applies OCR plus scene labeling to images and screenshots. [Chapter 1B](../1b-local-model/README.md)
uses the same helper.

Build the helper once, next to `classify_apple`, which looks for it there:

*Listing 1C.1: Building the helper*

```bash
swiftc -O extract_text.swift -o extract_text
```

Without the helper, PDFs and images are judged by filename alone.

## 1C.3 Running the pipeline

From `chapters/01-files-and-folders/`:

*Listing 1C.2: The whole private pipeline*

```bash
python3 make_mess.py practice/downloads
python3 verify.py snapshot practice/downloads

swiftc -O extract_text.swift -o extract_text
swiftc -O 1c-apple-foundation-models/classify_apple.swift -o classify_apple
./classify_apple practice/downloads                              # the on-device model reads the files
python3 make_plan.py practice/classification.json practice/downloads
python3 apply_plan.py --check practice/organize-plan.md practice/downloads
python3 validate_plan.py practice/claude-view.txt                # Claude sees metadata only
python3 apply_plan.py practice/organize-plan.md practice/downloads
python3 verify.py check practice/downloads
```

On an M4 Pro, all 28 files were labeled in about 18 seconds.

For a folder with thousands of files in subfolders, pass `--top-level` so that only loose files
are classified and each subfolder moves as one unit. See
[section 1.7](../README.md#17-folders-with-thousands-of-files).

```bash
./classify_apple practice/downloads --top-level
python3 make_plan.py --top-level practice/classification.json practice/downloads
```

## 1C.4 How it differs from 1B

| | 1B (LM Studio or Ollama) | 1C (Apple Foundation Models) |
|---|---|---|
| Setup | Install an app, download a model, start a server | None on macOS 26 or later |
| Language | Python, over HTTP | Swift, calling a system framework |
| Model | Your choice, any size that fits | One fixed model of roughly 3B parameters |
| Limits answers to the fixed lists with | A JSON schema containing enums | `@Generable` enums (guided generation) |
| Platforms | Mac, Windows, Linux | Apple Intelligence Macs only |
| Context window | You set it | Small, so each file is classified alone from its first 2 KB |

The fourth row shows one idea in two runtimes: constrain the output type, not the prompt. In
Swift, the enums are the schema.

*Listing 1C.3: The output types in `classify_apple.swift` (abridged)*

```swift
@Generable enum Category { case documents, images, spreadsheets, ... }
@Generable struct Classification { var category: Category; var sensitivity: Sensitivity }
```

The model cannot answer outside those types.

## 1C.5 Notes from building it

Use one session per file. A `LanguageModelSession` keeps its history, and the context window is
small. A fresh session also keeps one file from influencing the next.

The on-device model has its own safety guardrails, and they can refuse a file. The script
catches the error and leaves the file unlabeled, and `make_plan.py` treats an unlabeled file as
sensitive. A refusal cannot turn into "looks harmless". In our 60-file test, one file was
declined with the message "May contain sensitive content". It was sent to review, which is the
right outcome.

Do not run the classifier while the Mac is busy. On the same 60 files, our first run with PDF
extraction failed on 31 of them with a `SensitiveContentAnalysis` error, including installers
that had no extracted text. A 12B model was running at the same time. Run alone, 59 of 60
succeeded. The script now retries once and then fails closed. The general point is to check the
kind of error before blaming the data.

Expect over-caution. When unsure, the model was told to prefer a sensitive label, and it flagged
51 of the 60 real files, which makes `_sensitive/` the largest folder. Tighten the `@Guide`
text in the Swift file if that is too many for you.

Expect wrong labels too. On the fixture it filed a `.tar.gz` under Images and a to-do list under
`legal`. The metadata review and your own reading of the plan exist to catch these. The
[comparison in Chapter 1](../README.md#19-what-real-files-taught-us) has the numbers.

A single Swift file compiles with plain `swiftc`. No Xcode project and no `Package.swift` are
needed.

## Common tasks

Run from `chapters/01-files-and-folders`.

| I want to... | Run | How often |
|---|---|---|
| Build the classifier | `swiftc -O 1c-apple-foundation-models/classify_apple.swift -o classify_apple` | Once |
| Classify a folder | `./classify_apple <folder>` | Each folder |
| Classify only the top level | `./classify_apple <folder> --top-level` | Large folders |
| Build the PDF and image reader | `swiftc -O extract_text.swift -o extract_text` | Once |

## Exercises

1. Run 1B and 1C on the same folder and compare the plans.
2. Turn Apple Intelligence off in System Settings and run the classifier. What does the error
   say?
3. Add a file whose text the on-device model might refuse. Where does it end up?
