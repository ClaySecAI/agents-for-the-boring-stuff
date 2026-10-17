# Chapter 1D: Files by project, not by type

Sorting by type is how computers think about files. People think in projects. A mortgage
refinance is a pile of PDFs, spreadsheets and emails that belong together, and a folder called
`Documents` scatters them among everything else you have ever downloaded. When you open a real
Downloads folder, what you see is a handful of efforts: a house, a job search, a tax return, a
training plan, plus a drawer of installers.

[Chapter 1](../README.md) sorted by type and [Chapter 1B](../1b-local-model/README.md) did it
privately. This chapter changes the question the model answers. Instead of "what kind of file is
this?" it asks "which of my projects does this file belong to?"

## 1D.1 The design

A per-file classifier cannot find projects, because a project is a relationship between files and
a single file does not show it. The design below supplies what the classifier lacks.

You write the list of projects. A model running on your machine reads each file and assigns it to
one project from that list, or to `Unsorted`. The model's answer can only be a name from your list,
because the server limits it to an enum built from the list. As in Chapter 1B, the model has
nowhere to write free text, so file contents cannot leak through its output.

A file sometimes serves two projects. A conference expense report belongs to the trip and also
supports your tax return. A filesystem keeps one copy, so the file goes in a primary folder and
receives a Finder tag for each additional project. Click the tag in Finder and every file that
serves that project appears, wherever it is stored.

Sensitivity changes role. In Chapter 1B it chose the folder, so a mortgage file landed in
`_sensitive/financial/`, away from the rest of the refinance. Here the project chooses the folder
and sensitivity becomes a property of the project: it inherits the highest label among its files.
A ranked list tells you which projects to protect first.

Claude's part shrinks to what it can see without knowing anything private. It receives a table
with ids, extensions, sizes, dates and project numbers (`P1`, `P2`). It never sees file names or
project names, because a project called "identity theft case" is itself sensitive.

## 1D.2 What you need

Everything from Chapter 1B: a local model server (LM Studio or Ollama, installed as in
[Chapter 0B](../../00-getting-started/setup.md)) with a model loaded, Python 3.9 or later, and the
standalone `claude` command for the validation step. `python3 chapters/00-getting-started/check_setup.py`
reports what is missing. On macOS you also get
two extras, both optional:

- the website each file was downloaded from, which the model can use as a clue
- Finder tags for files that serve a second project

On other systems the pipeline still runs. It just has no download sources and writes the extra
projects to the plan's `Also` column without tagging anything.

## 1D.3 Writing the project list

The list is a JSON file you write yourself. A description of one sentence, naming the kinds of
documents the project holds, helps the model more than a clever name.

*Listing 1D.1: A project list (from the practice fixture)*

```json
[
  {"name": "Kitchen remodel", "description": "Renovating the kitchen at home: contractor quotes, permits, cabinets, tile, inspections."},
  {"name": "Tax prep", "description": "Preparing the 2025 tax return: income forms, receipts, payment vouchers."},
  {"name": "Software", "description": "Installers, updates and programs. Not part of any other project."}
]
```

A few rules:

- A name cannot contain `/`, `|`, `;` or `\`, and it cannot be `Unsorted`, which exists
  automatically.
- Include a project for utility files, such as `Software`, or the model will push installers into
  whichever project they came closest to.
- Start with the projects you can name. The model files everything else as `Unsorted`, and a large
  `Unsorted` pile is the signal that the list is missing a project.

Treat the file as private. Project names describe your life. `projects.json` and every output of
this chapter are listed in `.gitignore`, and the repository's commit guard refuses them by name.

### Why the list comes from you

The model can read a file and say what it is about. It cannot know which efforts in your life
matter, where one ends and the next begins, or what you want to call them. The list carries three
kinds of knowledge that no file contains:

- Which efforts exist. A Downloads folder holds the leftovers of dozens of small things. Only you
  know that six of them deserve a folder and the rest are noise.
- Where the boundaries are. A tax form can belong to a mortgage refinance or to your tax return.
  The right answer depends on how you will look for it later.
- What to call them. The names become folder names, tags and the words you search for.

The list also does a job for the machinery. It becomes the set of answers the model may give, which
is what stops it from inventing folders or leaking contents into its output. It has to choose from
your words.

### What the model can find on its own

If you do not know where to start, the model can propose a list. `suggest_projects.py` asks for a
short phrase describing the situation each file belongs to, then asks once for a handful of projects
that cover those phrases.

*Listing 1D.2: Asking the model for a first draft*

```bash
python3 suggest_projects.py practice-projects/downloads --show
```

We tested how good the draft is by letting the model write a list with no help from us, assigning
every file to its own list, and scoring the result against the answer key. The score ignores project
names, so a list the model invented can be compared fairly. It is cluster purity: for each group the
model made, credit the true project with the most files in it.

*Table 1D.1: Who wrote the list*

| Who wrote the list | Groups | Cluster purity | True projects recovered |
|---|---|---|---|
| You (the eight projects) | 8 | 100% | 8 of 8 |
| The model, told to think in projects | 10 | 88% | 7 of 8 |
| The model, with no steer | 10 | 92% | 7 of 8 |
| Sorting by file extension, best case | | 44% | |

Four things follow.

The model finds most of what is there. Seven of the eight real projects came back as groups, and
the purity is double what sorting by type can reach. A model-written list is a good first draft,
and it saves you from starting on a blank page.

It does not draw your lines. Its "Home Improvement" project absorbed two documents from the roof
repair claim, because both involve contractors. Whether a roof claim belongs with the house or with
insurance is exactly the kind of call only you can make, and the model made it silently. It also
invented projects that overlap ("Property Management", "Business Administration") and scattered the
conference trip across three groups.

Telling it to think in projects did not help the score. The instruction changed the names and
made the groups finer, but 88% against 92% is a difference of two or three files in single runs, so
read it as no difference. A cleverer prompt does not replace your own list.

The names are its own. They describe the files it saw, in its words. They are not the words you
will search for in six months.

Use the suggestions as a draft. Read them, delete the ones you do not need, merge the ones that
overlap, rename them, add the project it missed, and save your edited version as the list for
`assign_projects.py`. The tool does not print the proposed names unless you pass `--show`, because
the names describe your files. The one-line summaries it collects along the way are written to
`topics.json` beside the folder, and nothing leaves your machine.

### Writing a list that works

- Name efforts, not kinds of file. "Mortgage refi" is a project. "Loan documents" and "Invoices" are
  kinds of file, and they cut across every project you have.
- Describe each project in one sentence that names the documents it holds. The model leans on the
  description, and a project with no description gets files only when its name is obvious.
- Add a project for utility files, such as installers and updates, so that they do not get pulled
  into whichever project they resemble.
- Add a catch-all for things you own but did not plan around, such as product manuals. In our
  experiments the most damaging error was a file that matched no project being filed under a
  similar one (Table 1D.3). A catch-all gives those files a harmless home.
- Decide overlaps on purpose. When two projects share documents, say in the descriptions which one
  holds them ("pay stubs belong to Mortgage refi"), or accept that the file gets a tag for the other.
- Start with the five to ten projects you can name. You can add more after the first run.

### Treat the first run as a question

Run the assignment, then read two things: the `Unsorted` pile, and the files in each project that
do not belong. Each pattern you find points to a fix in the list.

- Several unsorted files about one subject mean a project is missing.
- A project that attracts files it should not mean its description is too broad, or a neighbouring
  project's description is too thin.
- Two projects that keep trading the same files mean the boundary needs a sentence in both
  descriptions.

On our real test folder, the first run exposed a missing project for product manuals and a stricter
rule was needed for files that match nothing. The list is a living document, and the second run was
better because the first one asked the right questions.

## 1D.4 Running it

The chapter ships a fixture: 59 invented files that belong to eight invented projects, plus an
answer key. Every document is addressed to the same fake person at the same fake address, so names
and addresses do not separate the projects. A few files have generic names and almost no content.

*Listing 1D.3: From a messy folder to an organized one*

```bash
cd chapters/01-files-and-folders/1d-projects
python3 make_project_mess.py                    # creates practice-projects/ with an answer key
python3 ../verify.py snapshot practice-projects/downloads

python3 assign_projects.py practice-projects/downloads practice-projects/projects.json
python3 link_files.py practice-projects/downloads practice-projects/projects.json practice-projects/assignments.json
python3 plan_projects.py practice-projects/assignments-linked.json practice-projects/projects.json practice-projects/downloads
python3 ../apply_plan.py --check practice-projects/organize-plan.md practice-projects/downloads
```

`link_files.py` is explained in section 1D.6. It writes `link-report.md`, which lists every group of
files it joined together and what it decided. Read that, then `organize-plan.md`, then
`protect-list.txt` to see which projects hold the most sensitive material. Send Claude the metadata
and, when you are satisfied, apply and verify:

*Listing 1D.4: The Claude gate, the move and the tags*

```bash
python3 ../validate_plan.py --prompt validator-prompt-projects.md practice-projects/claude-view.txt
python3 ../apply_plan.py practice-projects/organize-plan.md practice-projects/downloads
python3 ../verify.py check practice-projects/downloads
python3 tag_files.py practice-projects/organize-plan.md practice-projects/downloads    # macOS
```

Everything reverses. Remove the tags first, then undo the move:

```bash
python3 tag_files.py --remove practice-projects/organize-plan.md practice-projects/downloads
python3 ../undo_plan.py practice-projects/downloads
```

The scripts print counts and item numbers, not file names. Add `--verbose` to
`assign_projects.py` if you want names on screen.

### Folders and hidden items

A real Downloads folder holds subfolders as well as loose files, and each folder can be treated in
one of three ways.

| Option | How | What happens |
|---|---|---|
| Leave it where it is | `plan_projects.py --top-level --keep-folders` | The folder is untouched. Only loose files move. |
| Move it whole into a generic bucket | `plan_projects.py --top-level` | The folder moves unopened to `Folders/<name>`, intact. |
| Move it whole into its project | not built | The tool would sample the folder and place it in a project. |

Sorting the files inside a folder one at a time is the option to avoid. It breaks projects and
extracted installers, and it produces a plan with a hundred thousand rows that nobody can read.

Start by leaving folders alone. A folder can hold mixed material, such as an old backup or a shared
set of documents, so a single project label is a coarse choice. Developer folders and application
folders may be referred to by path from elsewhere on the machine, so moving them can break
something quietly. And one wrong placement hides far more files than a wrong file does. The loose
files are where a Downloads folder is untidy, and they are the safer place to begin.

Hidden items, meaning names that begin with a dot, are always left in place in top-level mode. They
belong to the system or to applications, and the plan still lists them with the same source and
destination so that the coverage check passes.

### Where the project folders go

By default the planner puts every project folder inside a folder named `Projects/`. Everything the
tool created then sits in one place, so you can see what it did at a glance, undo can remove exactly
that and nothing else, and a project can never merge with a folder you already had. We chose this
without asking, and on a real Downloads folder it turned out to be a choice worth asking about. Some
people would rather have `Taxes/` and `Mortgage refi/` directly in Downloads.

`--flat` does that. It leaves out `Projects/` and puts the project folders next to your own items. It
refuses to run when a project name matches an existing item, because the files would pour into your
folder. In that case, rename the project in the list or go back to the default.

## 1D.5 What the model sees

For each file the model gets four things:

| Signal | Where it comes from | What it is good for |
|---|---|---|
| File name | The file | Specific names such as `maplestone_quote_v2.pdf`; useless for `scan_0042.pdf` |
| Contents | The first 2 KB of text, or PDF text and OCR through the Chapter 1B helper | The strongest clue when the file has readable text |
| Download website | macOS records it when a browser or mail app saves a file | Places a bland "Thank you for your order" page with the shop that sent it |
| Last-modified date | The file | A hint that files from one effort arrive close together; it did not help in our tests (see 1D.7) |

The prompt also warns the model that many documents mention the same person and address, which
says nothing about the project. Without that line, a shared name pulls files toward whichever
project it saw first.

You can hide the website or the date with `--no-source` and `--no-dates`. The experiments below
use those flags to measure what each signal is worth.

## 1D.6 Linking files and holding empty ones

Running the pipeline on a real Downloads folder exposed two problems that the fixture had not.

### Files that share an account number

Three monthly statements from the same lender arrived. One carried a cue about the loan and landed
in the right project. The other two said only "Account number" and a table of payments, and were left
unsorted. The model judges each file alone, so nothing connected them. A shared account number is
strong evidence that files belong together.

`link_files.py` runs between assignment and planning. It:

1. finds identifiers that follow a keyword, such as "account number", "loan no.", "claim #" or "case ID"
2. links files that share one (an identifier found in more than 12 files is ignored, since a number
   that appears everywhere links nothing)
3. for each linked group whose members do not already agree, asks the local model once, showing it a
   piece of every member, which single project the group belongs to
4. gives every member that project

Groups whose members already sit in two or more different projects are left alone and counted as
conflicts. One bank account number can pay for a mortgage and a tax bill, and merging those would
be wrong. The report lists each group's members and what was decided, with file names for you and
nothing but counts on the terminal. Identifiers are never written anywhere.

Only numbers that follow one of those keywords count. Phone numbers, dates and bare digit strings
are ignored on purpose. Low precision here is costly, because a wrong link moves several files at
once.

### Empty files

A zero-byte file, or a tiny file holding only whitespace, cannot say which project it belongs to,
and filing it under `Unsorted` mixes "I could not tell" with "there is nothing here". These go to
`Projects/_Empty (review for deletion)/` instead. They are candidates for deletion, which is your
decision. Nothing in this chapter deletes a file. Claude's view marks them `PE`.

## 1D.7 Measuring it

The fixture comes with an answer key, so the pipeline can be scored. `score.py` counts how often a
file lands in its true project. It also computes a baseline: the best that sorting by file
extension could do, which is to take each extension and credit only the project with the most files
of that type.

We ran Gemma 4 12B in LM Studio on two versions of the fixture. The second, built with `--blind`,
replaces the text of every other file with a note that no text layer exists, the way a scanned PDF
looks when nothing can read it. Each cell is one run, scored out of 59 files.

*Table 1D.2: Files placed in the correct project*

| Signals the model saw | Readable text | Half unreadable |
|---|---|---|
| Name and contents only | 56 | 50 |
| Plus modified date | not run | 50 |
| Plus download website | not run | 55 |
| Plus website and date | 59 | 55 |

Sorting by extension, at best, reaches 44% (26 of 59 files), because `.pdf` alone spreads across
seven of the eight projects. Grouping by project reached between 85% and 100% in every configuration.

Five things stand out.

The misses are safe. Across all six runs, every wrong answer was a file left in `Unsorted`, and no
file went into the wrong project. The prompt tells the model to use `Unsorted` when it cannot tell,
and this model follows that. A pile of unsorted files costs you a few minutes of reading. A file
quietly filed under the wrong project can cost you much more, because you will not look there.

The download website was the signal that mattered. With it, five more files on the blind fixture
found their project, such as an order confirmation that says only "Thank you". The date added
nothing: the scores with and without it were identical. One plausible reason is that this model
does not weigh dates much. Another is that the fixture spaces each project's files only days
apart, which a model might not treat as evidence. We did not separate the two.

Secondary tags barely work. The fixture holds two files that serve a second project, and no run
found either. Two runs suggested one tag, and it was wrong. The prompt describes the `also` field as
"usually empty", and the model took it at its word. Exercise 4 asks you to change that and
watch recall and precision move against each other.

Claude's review has little to say. Given the metadata for the plan from the blind run, with all
signals, it approved. Four files in that plan belonged to projects and sat in `Unsorted`, but seven
unsorted items out of 59 look ordinary in a table of ids and dates. Nothing in the metadata says
which files were misfiled or missed. The check that finds them is you, reading the `Unsorted`
folder before you trust the plan.

Two of our own mistakes nearly produced wrong numbers, and both look like results until you check.
The first version of `--blind` wrote the same placeholder text into every blanked file. Identical
bytes hash identically, so the planner correctly reported 23 duplicates, and the plan looked
strange for a reason that had nothing to do with the model. Separately, one run crashed because we
applied a plan to the folder while it was still being read. When a number surprises you, look for
the experiment's fault before the model's.

### Files that belong to none of your projects

A real folder always holds files your list does not cover. We tested that with `--hold-out`, which
leaves one project off the list, so its seven files belong to none of the listed projects. The right answer is
`Unsorted`.

*Table 1D.3: Where the seven files of a missing project went*

| Project left off the list | Rule in the prompt | Files right (of 59) | Where the seven went | Filed under a wrong project |
|---|---|---|---|---|
| Marathon training (no similar project on the list) | original | 59 | all unsorted | 0 |
| Marathon training | stricter | 59 | all unsorted | 0 |
| Insurance claim (Kitchen remodel and Car purchase are close) | original | 54 | Kitchen 4, Unsorted 2, Car 1 | 5 |
| Insurance claim | stricter | 56 | Kitchen 2, Unsorted 4, Car 1 | 3 |

With no similar project on the list, the model leaves the files alone. With one nearby, it files
them there. The original prompt only said to use `Unsorted` when no project clearly fits, and five
of the seven roof-repair documents went to a kitchen remodel because both involve contractors. The
stricter rule adds a sentence saying that a topic none of the descriptions mentions belongs in
`Unsorted` even when a project is loosely related, with a recipe-and-fitness example. It cut the
wrong filings from five to three and cost nothing on the two main fixtures, which scored the same
as before (59 and 55 of 59).

Three of seven is still too many, and this is the failure that matters most. A file left unsorted is
visible. A file filed under the wrong project disappears into a folder you trust. The same thing
happened on a real folder, where bicycle manuals went into a fitness project. The reliable
protection is on your side: keep the project list close to complete, and include a catch-all such as
"Manuals and reference" for the things you own but did not plan around.

### Files linked by an account number

`--statements` adds three account histories that share one account number. The first says what the
account is for. The other two are tables of payments.

| | Files right (of 62) | The two bare statements |
|---|---|---|
| Per-file pass only | 60 | unsorted |
| After `link_files.py` | 62 | filed with the first statement |

Linking found two groups. One already agreed and needed no decision. In the other, a single group-level
question put all three statements in the same project. We built this fixture to match the problem we
had seen, so it shows that the mechanism works. It does not show how often real folders contain
groups like this.

The fixture is generated, not stored. Run `make_project_mess.py` to build it. Add `--blind` for the
harder version, `--hold-out PROJECT` to leave a project off the list, and `--statements` for the
linked account histories.

## 1D.8 Finder tags

`tag_files.py` reads the plan's `Also` column and gives each listed file one Finder tag per extra
project. It keeps any tags the file already has, and `--remove` takes off only the ones it added.
`--check` reports what it would do without changing anything.

Tags are stored as an extended attribute on the file, and the tag name is visible in Finder. If the
folder lives in iCloud Drive, the tag names may sync. A tag named after a sensitive project says
that the project exists, so think before tagging files in a synced folder.

## 1D.9 Teaching it by correcting it

The model will leave some files in Unsorted and will put a few in the wrong project. You can fix
those by hand, but the same kind of file will come back next month. `teach.py` turns each fix into
something that lasts.

```bash
python3 teach.py <folder> projects.json assignments.json
```

It walks through the files the model left unsorted (or every file, with `--all`). For each one it
prints the name, the website it was downloaded from, the date and the start of the contents, and you
type a project number, `u` to keep it unsorted, Enter to skip, or `q` to stop. Run it in your own
terminal: it shows you the contents of your files, which is the point. Your answers are saved to
`corrections.json`.

`rules.py learn` then looks for what the corrected files have in common with each other. A rule is an
exact match on one of four things: an account or case number in the text, the file's exact path, the
website it came from, or its name with digits and punctuation removed (so `account_history (2).pdf`
and `account_history (7).pdf` share a pattern). A rule needs agreement. A number or a path needs one
example. A website or a name pattern needs two, and all of the examples must name the same project. A
bank you use for both taxes and a mortgage therefore makes no rule, because the website tells you
nothing about which project a file belongs to.

```bash
python3 rules.py learn <folder> projects.json corrections.json --assignments assignments.json
python3 rules.py apply <folder> assignments.json rules.json
```

`learn` prints a preview: how many files a rule would decide and how many of those would change.
`apply` writes `assignments-ruled.json`, which goes into `plan_projects.py` as usual. Files that a rule
decided are marked `"source": "rule"`. If two rules point at different projects for one file, neither
wins and the model's answer stands.

The tests cover this without a model. The test fixture has two labelled files per project; the rules
learned from them decide more than twenty others, and none of those decisions is wrong. That is a
property of the fixture, whose bank statements share a website and an account number, and a messier
folder will give you weaker rules. The preview is how you find out before anything moves.

Rules name your websites, account numbers and projects. `rules.json` and `corrections.json` are
ignored by git and refused by the commit guard.

## 1D.10 Renaming files

Moving a file to the right project does not fix `scan0042.pdf`. `suggest_names.py` asks the local
model for a short title and builds a name from it: `2024-03-08 Lease renewal.pdf`. The date is the
file's modified date and the extension is the original one.

```bash
python3 suggest_names.py <folder>                  # writes names.json
python3 plan_projects.py --names names.json ...    # puts the new names in the plan
```

By default it renames only files whose names say nothing: camera and scanner names, `Document (3)`,
`Untitled`, a long run of hex digits, a number. A name you chose, like `Resume - Clay.pdf`, stays
unless you pass `--all`. Unsorted and empty files keep their names, because a rename without a
project is guesswork on guesswork.

This is the one place in the chapter where the model writes free text instead of picking from a list.
It runs on your machine. The title is cleaned before it can become part of a path: only letters,
digits, spaces and a few punctuation marks survive, and the length is capped. The new names appear in
the To column of `organize-plan.md`, so you read them before anything is renamed, and `undo_plan.py`
restores the old ones. Claude does not see them: `claude-view.txt` has no names.

## 1D.11 Beyond the Mac

Reading the text of a PDF or a scan used to depend on the Swift helper, which needs PDFKit and Vision.
On other systems `classify_local.py` now falls back to open-source tools when they are installed:
`pdftotext` (from poppler) for the text layer of a PDF, and `tesseract` for images and for PDFs that
are scans (`pdftoppm` renders the first page). If none is installed, the file is judged by its name
and extension, as before. Nothing fails. On Debian or Ubuntu that is
`apt install poppler-utils tesseract-ocr`; with Homebrew, `brew install poppler tesseract`.

Finder tags are macOS only. On other systems the Also column still records the extra projects, and
`link_files.py` still works, but `tag_files.py` does nothing useful.

## 1D.12 Choosing a model

`bakeoff.py` runs the same assignment task, prompts and scoring against several models, one after
another, and prints a table. Three synthetic fixtures, 59 files each: the readable one, one where
file names are replaced with scan numbers (`--blind`), and one with a project hidden from the list
(`--hold-out`). Numbers are files placed in their true project.

| Model | Readable | Blind | Hold-out | Wrong-project (total) | Seconds per file |
|---|---|---|---|---|---|
| gemma-4-e4b | 56 | 53 | 57 | 1 | 0.7 |
| qwen3.5-9b | 57 | 54 | 53 | 7 | 1.2 to 2.0 |
| gemma-4-12b | 59 | 55 | 56 | 3 | 1.8 |
| Apple on-device model | 51 | 47 | 54 | 8 | 1.0 |
| phi4 14B (Ollama) | 58 | 55 | 54 | 4 | 1.4 to 1.5 |
| granite4.1 8B (Ollama) | 57 | 52 | 56 | 3 | 0.8 to 0.9 |
| ministral-3 8B (Ollama) | 56 | 52 | 52 | 5 | 0.9 to 1.0 |
| llama3.2 3B (Ollama) | 52 | 48 | 47 | 24 | 0.4 to 0.5 |
| nomic-embed-text v1.5 (embeddings only) | 42 | 31 | 43 | 10 | 0.02 |
| EmbeddingGemma 300M (embeddings only) | 51 | 46 | 51 | 11 | 0.03 |
| Qwen3-Embedding 0.6B (embeddings only) | 53 | 46 | 47 | 14 | 0.05 |

Ollama's phi4 (14B, `ollama pull phi4`, run in the bake-off as `ollama:phi4`) landed beside gemma-4-12b: the
same speed, one more file right on the readable fixture, and four misfiled on the hold-out one.

Three more Ollama models followed. granite4.1 8B and ministral-3 8B sit just behind the best LM Studio
models and run in under a second per file. llama3.2 3B is the cautionary row: it is the fastest and
misfiled 24 files, more than any other model, so small is not the same as safe. The count of
misfiled files, not the count of right ones, is what separates these models.

Apple's on-device model, run through the `assign_apple` helper, placed fewer files correctly than
the 8B to 14B models and misfiled eight. It needs nothing installed or downloaded and runs at about a
second per file, so it suits a Mac where you will not set up a server. Its context window is small, which
is why long project lists suit it less well than a large model.

Three things stand out. The smallest model is nearly as accurate as the others at a third of the
time, and it almost never files something under the wrong project; it declines instead. That is the
right way to be wrong, because an unsorted file costs you a glance and a misfiled one costs you a
search. The hold-out fixture is where models differ: two of the three, given a file that fits none of
your projects, picked one anyway (6 and 3 files).

The embedding rows answer "can a small specialist replace the language model?" Not alone, but the
newer ones come close enough to matter. Embeddings place a file by similarity to each project's
description, run roughly forty times faster, and need no prompt. The embedding rows use a margin of
0.03: the best project must beat the second by that much, or the file stays unsorted. Nomic left a
third of the files unsorted and misfiled ten more. EmbeddingGemma (333 MB) and Qwen3-Embedding
(639 MB) placed 46 to 53 of 59 correctly in every fixture, with 11 and 14 misfiled across the three,
against 1 to 7 for the language models. With no margin at all they place every file and get
6 to 14 wrong per fixture, so the margin is doing real work. The remaining gap is the same one as
before: statements from different accounts at one bank look alike. Giving embeddings example files
made things worse, since the shared boilerplate drowned the signal. Their natural use is a cheap
first pass whose confident answers you keep and whose doubts go to a language model;
`embed_assign.py` is there to try that, and it takes `--preset embeddinggemma` or `--preset qwen3`.

Small models built for documents exist, such as Donut, LayoutLM and the Florence family, but they
identify layout and fields (this is an invoice, here is the total), not which of your projects a file
serves, and most expect a page image rather than text. For this task the embedding models
(EmbeddingGemma, Qwen3-Embedding) are the nearest fit, and they are the two extra rows above.
Treat the numbers as one machine, one afternoon and a synthetic folder, not a ranking.

### Running the comparison yourself

The comparison script needs the models you want to test, installed as in
[Chapter 0B](../../00-getting-started/setup.md), and the three practice folders from section 1D.7
(`make_project_mess.py` builds them). From this folder:

```bash
python3 make_project_mess.py practice-projects/downloads
python3 make_project_mess.py practice-blind/downloads --blind
python3 make_project_mess.py practice-holdout2/downloads --hold-out "Insurance claim"
```

Download each model first, then name it in `--models`:

```bash
lms get google/gemma-4-e4b                 # an LM Studio model
ollama pull granite4.1:8b                  # an Ollama model (the server must be running: ollama serve)
swiftc -O assign_apple.swift -o assign_apple   # the Apple helper (macOS 26+, Apple Intelligence on)

python3 bakeoff.py --models google/gemma-4-e4b ollama:granite4.1:8b apple:./assign_apple \
    --fixtures practice-projects practice-blind practice-holdout2
```

LM Studio models are named by the keys `lms ls` prints, Ollama models by `ollama:` plus the name
`ollama list` prints, and Apple's by `apple:` plus the path to the helper. The script loads each LM Studio
model itself, runs the three fixtures, and prints a table. Results are saved to `bakeoff-results.json`,
and rerunning skips what is already done. Each model takes between a minute and a few minutes per
fixture. Add `--embed text-embedding-nomic-embed-text-v1.5` to include an embedding model.

## 1D.13 Protected and synced folders

Everything so far ran against a folder an ordinary program can read. Three common folders are not like
that: your iCloud Drive, and any folder under Desktop, Documents or Downloads on a Mac, and any folder
that syncs to another service. We sorted an iCloud Downloads folder of 411 files, and four things
went wrong that the book's earlier chapters would not have warned you about.

### macOS blocks programs from protected folders

macOS asks you before it lets a program read Desktop, Documents, Downloads, iCloud Drive or removable
drives. The permission belongs to the application that started the program, not to the program. In
our run, Python started from the terminal panel inside the Claude app failed with `PermissionError:
Operation not permitted` on the iCloud folder, while the same command in Terminal.app worked. The check
that ran inside the agent's own shell could read the folder, which shows how confusing this gets:
three terminals on one Mac, three different answers.

To find out which one you have, run any read command (`ls "<folder>"`) in the terminal you plan to use.
If it fails with "Operation not permitted", give that application access in System Settings, under
Privacy & Security, then Files & Folders (for one folder) or Full Disk Access (for everything). Quit and
reopen the application afterward. Grant the narrowest permission that works, and only to an application
you trust, since Full Disk Access lets everything it launches read every file you own.

### Files that are not on disk

iCloud keeps some files in the cloud and leaves a placeholder on your Mac. A script reading a placeholder
forces a download, and the local model cannot judge a file it cannot read. Count them first:

```bash
find "<folder>" -type f -flags +dataless | wc -l
```

If the number is not zero, select the folder in Finder, choose Download Now from the context menu, and
count again. In our folder, 222 of 412 files were cloud-only. Sorted by name alone, half the folder
would have gone to Unsorted.

### The scripts write hidden files, and they sync

`apply_plan.py` saves a copy of the plan so undo can find it, and `verify.py` saves a snapshot of file
hashes. Both are written beside the folder you give them, and both contain file names. Beside an iCloud
Downloads folder is the root of iCloud Drive, so they would sync to every device you own. Set
`PLAN_STATE_DIR` to a local folder and every script that reads or writes these records uses it:

```bash
export PLAN_STATE_DIR="$HOME/Documents/icloud-downloads-state"
```

Set it again, with the same value, whenever you run `verify.py` or `undo_plan.py` on that folder.
The project list, assignments and plan should live outside the synced folder too. We kept them in a
scratch folder.

### Moves and tags sync as well

iCloud pushes every move to your other devices, so a bad plan lands everywhere. Back up first to a plain
local folder, and check that the copy is exact, with matching file counts and hashes. Finder tags sync
too, so a tag named after a sensitive project shows that the project exists. Decide before tagging.

### Running it without a person in the loop

The question these folders raise is whether the whole job could run on a schedule, with nobody at the
keyboard. Parts of it can, and the line between them is the book's own rule.

*Gathering and proposing can run unattended.* Assigning files to projects, building the plan, running the
coverage check and asking Claude to review the anonymous table change nothing. Scheduled with launchd
(`~/Library/LaunchAgents`, a property list that names the command and the time), they produce a plan and
a report for you to read later. Two requirements follow from the sections above. The program the job
launches needs the macOS permission, so grant it to the interpreter or to a small launcher script you
trust, not to Terminal as a whole. And the model server must be running when the job starts, because
nothing will load it for you.

*Applying should wait for a person, or for gates you wrote in advance.* The agent that built this chapter
was stopped by the permission system when it tried to move files in the real folder, even though the
request came from the user. That is the system working as designed: a move you cannot easily reverse is
the step a person should own. If you decide a task is routine enough to apply without asking, make the
decision explicit in code rather than in the agent's judgment, and refuse to apply unless every gate
passes:

- the coverage check passes and nothing is skipped
- the number of moves is within a limit you set, such as 300
- no file moves out of a folder you listed as protected, and no sensitive file moves at all
- the backup copy exists and its hashes match
- the undo record is written to a local folder before the first move
- `verify.py` runs afterward, and a failure sends you a notification and runs the undo

For Claude Code itself, headless runs use `claude -p`, and `.claude/settings.json` can allow exactly the
scripts the job needs and nothing else, the same way this repository denies `rm`. A job that is allowed to
run `assign_projects.py` and `plan_projects.py` but not `apply_plan.py` cannot apply by accident.

Section 1D.14 builds that unattended version.

## 1D.14 A weekly sweep

`sweep.py` is the unattended version for a folder you have already sorted once. The first sort looked at
everything and a person approved a plan. A sweep handles only what arrived since: the loose files sitting
directly in the folder. It files each into the matching project folder that already exists, leaves
everything else where it is, and replaces the approval with gates written in code.

```bash
python3 sweep.py init ~/Downloads        # writes a config and a project list from your existing folders
```

`init` creates `~/Library/Application Support/downloads-sweep/config.json` and `projects.json`, with one
entry per folder it found. The descriptions say `EDIT ME`. Open `projects.json`, delete the folders that are
not projects, and write a real sentence for each of the rest. The model files by those sentences, so this
is where the quality comes from. Then try it without moving anything:

```bash
python3 sweep.py run --dry-run
python3 sweep.py status
```

**What a sweep does.** It skips hidden files, subfolders, empty files, partial downloads
(`.crdownload`, `.download`, `.part`), iCloud placeholders, and anything changed in the last hour, since a
file still being written is not ready. It starts the model server and loads the model if they are not
running, assigns each remaining file to one of your projects, and then applies the gates. It unloads the
model and stops the server it started when it finishes. A macOS notification reports counts, never names.

**Folders that are not projects.** A sweep never opens a subfolder, so each folder that is not a project
needs a decision, and there are three. Move it whole into a project (a folder of event photos from one
photographer belongs in a cycling photos project as a unit). Sort its files one at a time (an
`attachments` folder holds income papers, police reports and lease emails that belong in four different
projects). Or leave it. A sweep supports the first directly, through `folder_rules` in `config.json`:

```json
"folder_rules": {"EventPhotos Download (123456789)": {"unit": "Cycling event photos"}}
```

The folder moves, unopened, into the project's folder, and the sweep's undo restores it like any other
move. A folder with no rule is left alone and counted in the report as untracked. `python3 sweep.py
folders` lists them, so nothing sits in the folder forgotten. The second case is a separate, approved run
like the rest of this chapter: assign the files in that folder with `assign_projects.py`, write a plan
whose destinations climb out of the folder (`../Taxes/2021 W2.pdf`), check it with `apply_plan.py
--check`, and apply it. A sweep does not do this one for you, because a folder that mixes projects is
exactly the case where a person should read the plan.

Note that `verify.py` cannot confirm this kind of run: it looks only inside the folder it was given, so files moved out show up as lost. Hash the files at their new locations and compare them with the snapshot instead; in our run all 33 files matched.


**The gates.** Files the model cannot place stay put. Files it labels `credentials`, or cannot label at all,
stay put and are counted, because a key file filed in the wrong folder is hard to find again; change
`hold_sensitivities` in `config.json` to hold more kinds, such as `government_id`. A sweep that would move more
than `max_moves` files (100 by default) moves none and says so, since a sudden flood usually means
something changed. A file is never overwritten: a name already taken gets `(2)`. The plan must pass
`apply_plan.py --check`, the undo record is written before the first move, and afterward every moved
file is hashed again. One mismatch undoes the whole sweep.

**Undo.** Each sweep keeps its own folder of records under the state directory:

```bash
python3 sweep.py undo            # the latest sweep
python3 sweep.py undo 2026-10-17-093819-255   # a named one
```

**Tests.** `test_sweep.py` runs the whole thing against a small fake model server, so it needs no model:
files filed into existing folders and nothing else touched, undo, the dry run, the move limit, a missing
server, and a second sweep with nothing new. We also ran a sweep with a real model, gemma-4-e4b, on a
practice folder with the same layout as an organized Downloads: 56 of 59 files ended where the
fixture's answer key puts them, and undo restored all 59.

**Scheduling it.** A laptop is not always on at 03:00, and launchd treats the cases differently. A job
missed while the Mac was asleep runs when it wakes. A job missed while the Mac was powered off does not
run at the next start. So the job that `agent` prints does not ask for "Sundays at 03:00". It asks launchd to
run at 03:00 every day and at every login, and passes `--if-due 7`, which makes the sweep do nothing unless
seven days have passed since the last real one. Dry runs and stopped sweeps do not count, so a week
that failed for a missing permission or a model that would not load tries again the next day. A Mac that
is usually shut at night sweeps on the first login after a week has gone by.

```bash
python3 sweep.py agent > ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
launchctl load ~/Library/LaunchAgents/local.boringstuff.downloads-sweep.plist
```

Before you do, resolve the permission from section 1D.13. The job launches your Python, and macOS asks the
launching program for access to Downloads when it first runs. Run `python3 sweep.py run` once from the terminal
you will grant access to and look for a "would like to access files in your Downloads folder" prompt. A job
that fails for lack of permission stops cleanly with nothing moved and a notification saying so. To turn
the schedule off, `launchctl unload` the same file and delete it.

**What a sweep cannot catch.** The gates stop floods, overwrites, lost files and sensitive labels. They do
not stop a wrong filing: a sweep with a vague project description will cheerfully file a lease into
Taxes. Check the `status` output now and then, open a project folder, and tighten a description when
something lands wrong. Because every sweep is separately undoable, a bad week costs one command.

## 1D.15 Limits

- The model only knows the projects you list. A project you forgot ends up in `Unsorted`, or worse,
  inside a similar project. `suggest_projects.py` can propose a draft, but it works from phrases
  the model wrote about each file, and in our test it merged one project into another and missed a
  third. A sturdier approach to discovery would embed each file's text and cluster the embeddings.
  This chapter does not do that.
- Each file has one primary project. The tag covers the second, but the folder structure still
  forces a choice.
- Linking trusts numbers that follow a keyword such as "account number". It misses identifiers
  printed differently, and it can join files that merely share a number. The conflict check catches
  one case: when members already point to two different projects. It cannot catch a wrong link
  between files that were all unsorted.
- Off-list files are the worst failure. A file that belongs to none of your projects can still be
  filed under a similar one (Table 1D.3). Reading the plan is the check.
- The fixture is easier than a real folder in some ways and harder in others. Its documents are
  short and clean, and its projects are clearly distinct. Real projects overlap, run for years and
  contain files with no readable text.
- Results come from single runs of one 12B model on 59 files. Treat the numbers as an illustration
  of the method, not a measurement of the model.
- Project names are sensitive. The Claude validator sees only ids, which also limits what it can
  check: it can find dates and sizes that look wrong but cannot judge whether a file belongs.

## Exercises

1. Write a project list for your own Downloads folder, assign without moving anything, and read the
   protect list. Which project surprises you?
2. Run the assigner on the fixture with `--no-source` and again with `--no-dates`. Which signal
   matters more, and does the answer change on the `--blind` fixture?
3. Make the descriptions in `projects.json` vaguer. How much does accuracy fall?
4. Run `suggest_projects.py` with `--framing none` and with `--framing projects`, three times each.
   How much do the proposed lists vary from run to run? What does that say about trusting a
   single suggestion?
5. Take one model-written list and edit it by hand into the list you would actually want. What did
   you change, and what does that tell you about what the model could not know?
6. Change the `also` instruction in `assign_projects.py` so the model proposes secondary projects
   more readily. Does recall rise, and what happens to precision?
7. Hold out each project in turn with `--hold-out`. Which ones have a neighbour on the list that
   attracts their files, and which are left unsorted?
8. Add a catch-all project such as "Everything else" to a hold-out run. Do the held-out files go
   there, and do files that belong to real projects start going there too?
9. Run the `--statements` fixture with `--max-share 2`. What changes, and why?

## Further reading

Chapter 1B explains the local model setup and the constrained output this chapter reuses.
[Chapter 1, section 1.7](../README.md#17-folders-with-thousands-of-files) covers folders too large
to plan file by file.
