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

Everything from Chapter 1B: a local model server (LM Studio or Ollama) with a model loaded, Python
3.9 or later, and the standalone `claude` command for the validation step. On macOS you also get
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

## 1D.4 Running it

The chapter ships a fixture: 59 invented files that belong to eight invented projects, plus an
answer key. Every document is addressed to the same fake person at the same fake address, so names
and addresses do not separate the projects. A few files have generic names and almost no content.

*Listing 1D.2: From a messy folder to an organized one*

```bash
cd chapters/01-files-and-folders/1d-projects
python3 make_project_mess.py                    # creates practice-projects/ with an answer key
python3 ../verify.py snapshot practice-projects/downloads

python3 assign_projects.py practice-projects/downloads practice-projects/projects.json
python3 plan_projects.py practice-projects/assignments.json practice-projects/projects.json practice-projects/downloads
python3 ../apply_plan.py --check practice-projects/organize-plan.md practice-projects/downloads
```

Read `organize-plan.md`, then `protect-list.txt` to see which projects hold the most sensitive
material. Send Claude the metadata and, when you are satisfied, apply and verify:

*Listing 1D.3: The Claude gate, the move and the tags*

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

## 1D.5 What the model sees

For each file the model gets four things:

| Signal | Where it comes from | What it is good for |
|---|---|---|
| File name | The file | Specific names such as `maplestone_quote_v2.pdf`; useless for `scan_0042.pdf` |
| Contents | The first 2 KB of text, or PDF text and OCR through the Chapter 1B helper | The strongest clue when the file has readable text |
| Download website | macOS records it when a browser or mail app saves a file | Places a bland "Thank you for your order" page with the shop that sent it |
| Last-modified date | The file | A hint that files from one effort arrive close together; it did not help in our tests (see 1D.6) |

The prompt also warns the model that many documents mention the same person and address, which
says nothing about the project. Without that line, a shared name pulls files toward whichever
project it saw first.

You can hide the website or the date with `--no-source` and `--no-dates`. The experiments below
use those flags to measure what each signal is worth.

## 1D.6 Measuring it

The fixture comes with an answer key, so the pipeline can be scored. `score.py` counts how often a
file lands in its true project. It also computes a baseline: the best that sorting by file
extension could do, which is to take each extension and credit only the project with the most files
of that type.

We ran Gemma 4 12B in LM Studio on two versions of the fixture. The second, built with `--blind`,
replaces the text of every other file with a note that no text layer exists, the way a scanned PDF
looks when nothing can read it. Each cell is one run, scored out of 59 files.

*Table 1D.1: Files placed in the correct project*

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

The fixture is generated, not stored. Run `make_project_mess.py` to build it, and add `--blind`
for the harder version.

## 1D.7 Finder tags

`tag_files.py` reads the plan's `Also` column and gives each listed file one Finder tag per extra
project. It keeps any tags the file already has, and `--remove` takes off only the ones it added.
`--check` reports what it would do without changing anything.

Tags are stored as an extended attribute on the file, and the tag name is visible in Finder. If the
folder lives in iCloud Drive, the tag names may sync. A tag named after a sensitive project says
that the project exists, so think before tagging files in a synced folder.

## 1D.8 Limits

- The model only knows the projects you list. A project you forgot ends up in `Unsorted`. A natural
  next step is discovery: embed each file's text, cluster the embeddings and let the model name the
  clusters, so it can suggest projects you did not list. This chapter does not do that.
- Each file has one primary project. The tag covers the second, but the folder structure still
  forces a choice.
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
4. Change the `also` instruction in `assign_projects.py` so the model proposes secondary projects
   more readily. Does recall rise, and what happens to precision?
5. Add a ninth project to the fixture and leave it off the list. Where do its files go?

## Further reading

Chapter 1B explains the local model setup and the constrained output this chapter reuses.
[Chapter 1, section 1.7](../README.md#17-folders-with-thousands-of-files) covers folders too large
to plan file by file.
