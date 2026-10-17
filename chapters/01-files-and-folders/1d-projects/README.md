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

## 1D.9 Limits

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
