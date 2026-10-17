# Chapter 8 plan: A model that reads your commits (not yet a chapter)

This is a design note for a candidate chapter. It contains no code. It settles the decisions a
chapter would need before anything is built: where the model runs, what it may and may not do, what
it should look for, what it prints, when it runs, how it fails and how to measure it.

## 8.1 The idea

The repository already has three layers that stop personal data before it reaches GitHub:

1. `.gitignore`, which asks git to skip practice folders and generated files.
2. The repository's own pre-commit hook, `scripts/check_repo_clean.py`: an allowlist of file types,
   fixed patterns (home paths, email addresses, numbers shaped like social security numbers, keys)
   and a private blocklist kept in `.git/private-terms.txt`.
3. A global hook in `~/.config/git/hooks` that runs gitleaks, then a second personal-data check (a
   whole-word blocklist, the home path and noreply addresses), then the repository's own hook.
   Repositories that are meant to hold personal data opt out with
   `git config hooks.allowPersonalData true` and may push only to private repositories.

All three are rules. A rule finds what someone thought to write down. It does not find a friend's
name that is not on the blocklist, a sentence about a diagnosis, or a fixture that was meant to be
made up and turned out to be a real address. Those are judgments about meaning, and judging meaning
at scale is the job this book gives to a model.

So the proposal is a fourth layer: before a commit or push, a local model reads the lines being
added and answers one question. Does anything here look like real personal data that the rules
missed?

The chapter would use the book's usual division of labor. The model supplies judgment. Plain code
supplies guarantees: what the model is shown, what shape its answer must take, and what happens with
that answer. You supply the decision about what counts as private, through the blocklist and through
reading what the model flags.

## 8.2 Where the model runs

**Default: a local model.** Either LM Studio or Ollama as in
[Chapter 1B](../01-files-and-folders/1b-local-model/README.md), or Apple's on-device model as in
[Chapter 1C](../01-files-and-folders/1c-apple-foundation-models/README.md). The reviewer exists
because the diff might contain personal data. Sending that diff to a hosted model to ask whether it
contains personal data copies the data to a third party before the question is answered. That
defeats the purpose.

On a Mac, Apple's on-device model is the better default for this job in particular. It needs no
server, so there is nothing to start before a commit, and there is no server log to clean up (see
8.6). Its context window is small, which suits a hook that should only ever see a short diff. LM
Studio or Ollama are the default everywhere else, and on a Mac when you want a larger model.

**A hosted model is acceptable only in narrow cases, and never by default:**

- Never when `hooks.allowPersonalData` is set. That setting means the repository holds personal data
  on purpose. The hook should read it and refuse to send anything off the machine.
- Otherwise, only when you turn it on explicitly for one repository, for example with a git config
  setting, and only for repositories whose content you would be willing to publish anyway. The
  question it answers then is "did I slip?" and not "is this private?".
- Never as a fallback when the local model is down. A fallback that quietly sends the diff elsewhere
  is the same leak with an extra step.

The chapter should state the same rule as Chapter 0.5: each stage says who sees what.

## 8.3 The trust boundary

The diff is untrusted input. Any file can contain text addressed to the model, such as a comment
saying that this commit has been checked and should be approved. Chapter 0.4 describes this as
prompt injection, and its defense applies here unchanged: do not try to write a cleverer prompt;
limit what the model can do.

The reviewer is designed so that it can only add a warning or a block. It cannot remove one.

- **One call, no tools, no loop.** The reviewer is a single request to a model with no tools. It
  cannot read other files, run commands or reach the network. An "agent" that can run commands
  while reading untrusted text is exactly the scenario Chapter 0.4 warns about, and this design
  deliberately is not one.
- **It runs after the rules, and the rules decide first.** If `check_repo_clean.py`, gitleaks or the
  global check refuses the commit, the commit is refused. The reviewer is not asked. Nothing the
  model returns can turn a refusal into an approval.
- **It sees only added lines.** The hook takes the `+` lines of the staged diff, for allowlisted text
  files only. Removed lines are never sent: removing data is the outcome we want, and leaving them
  out roughly halves the prompt.
- **Its answer has a fixed shape.** The request carries a JSON schema, as in Chapter 1B. `category`
  is an enum and `confidence` is a number between 0 and 1. There is no free-text field such as
  `reason`. A free-text field is the channel through which matched text, or injected text, would
  reach your terminal. The parser drops anything outside the schema and treats an answer that does
  not parse as a failure (8.6), not as "no findings".

With those limits, the worst a successful injection can do is one of two things:

1. **Suppress a finding.** The model says nothing about a real leak. That is the same outcome as
   having no reviewer, and the rules have already run.
2. **Invent a finding.** The model flags a clean line. That costs the person committing a moment
   to look at their own line. It is a nuisance, not a leak.

Neither is worse than the baseline without a reviewer. This is the property the chapter should
test (8.7), not assume.

## 8.4 What it should catch, and what it should ignore

The model is there for what a pattern cannot express. Its categories, as a fixed list:

| Category | Examples of what it should catch |
|---|---|
| `person_name` | A real-looking full name that is not on the blocklist, especially beside a relationship ("my sister", "our accountant") |
| `health` | A diagnosis, medication, appointment or test result described in prose |
| `financial` | A balance, salary, account detail or debt described in prose, not just a number shape |
| `address` | A street address, or a place precise enough to locate a person |
| `internal_host` | A hostname, share name or service on a private network, such as a `.lan` or `.internal` name, or a NAS share |
| `real_fixture` | Fixture data that looks real: a plausible name, address and date of birth together, where the fixtures use obviously made-up values |
| `real_filename` | A file name that describes a real document or person, such as a tax form with a year, or a clinic's name |
| `other_personal` | Anything else that identifies a real person and fits none of the above |

What it should ignore, and the prompt should say so:

- The made-up people and places the fixtures use, such as "Jordan Lee", and addresses on
  `example.com` or `example.org`.
- Documentation of what the guards look for. A sentence such as "the guard blocks home-directory
  paths" describes a pattern; it does not contain one.
- Generic placeholders: `<your-username>`, `your-model`, `~/Downloads`.
- Public names in a public role: authors and books in a credits section, product and company names
  such as LM Studio or Apple.
- Anything the rules already catch. The reviewer is not a second regex. If the hook sees a finding
  on a line the rules would have flagged, that is a sign the rules were bypassed, which is worth a
  warning of its own.

The false-positive list matters as much as the catch list. This repository is a book about personal
data, so its prose talks about tax returns, medical bills and identity documents constantly. A
reviewer that flags every mention of the word "medical" will be switched off within a week.

## 8.5 What it prints

The output matches the existing guards: where, never what.

Each finding the model returns has four fields:

| Field | Type | Notes |
|---|---|---|
| `file` | string | Must be one of the files in the diff; anything else is dropped |
| `line` | integer | A line number in the new version of the file; must be one of the added lines |
| `category` | enum | One of the categories in 8.4 |
| `confidence` | number | 0 to 1 |

The hook checks `file` and `line` against the diff it sent, so a model that invents a location
produces nothing. It then prints one line per finding:

```
WARNING: 2 possible personal details the rules did not catch (local model, not the rules).
  chapters/02-text/README.md: line 41 may contain a person_name (confidence 0.82)
  chapters/02-text/make_text_mess.py: line 17 may contain an address (confidence 0.64)
Look at those lines yourself. The matched text is not printed.
```

The matched text is never printed, for the same reason as in `check_repo_clean.py`: terminal output
ends up in scrollback, CI logs and pasted bug reports.

Findings are printed, not written to a file. If a chapter later needs to save them, they go in a
`practice*` folder, and the name must avoid the guard's list of generated-output names (`review*.md`
is already on it).

## 8.6 When it runs, how fast, and how it fails

**Pre-commit or pre-push.** Both, with different strictness:

- **Pre-commit: warn.** It runs often, so it must be fast and must not get in the way. It prints
  findings and lets the commit through. A commit is still local and can be amended.
- **Pre-push: block on high confidence.** A push is the step that cannot be taken back once the
  remote is public. The pre-push hook also knows the remote's URL, which pre-commit does not, so it
  can apply the strict mode only when pushing to a public repository. That fits the split the global
  hook already makes between public and private remotes.

**Size caps.** Only added lines, only allowlisted text files, and only up to a fixed budget per run
(on the order of a few thousand tokens, which suits the small context windows in 1B and 1C). Files
are sent one at a time, each in a fresh session, as Chapter 1C does with `LanguageModelSession`, so
one file's text cannot influence the judgment of another. A diff over the budget is not truncated
silently: the hook says how many lines it did not read. A large commit, such as a generated fixture,
is a reason to look at it yourself.

**Confidence to action.** Starting thresholds, to be set from the evaluation in 8.7, not from intuition:

| Confidence | Pre-commit | Pre-push to a public remote |
|---|---|---|
| Below 0.5 | Nothing printed | Nothing printed |
| 0.5 to 0.8 | Warning | Warning |
| 0.8 and above | Warning | Block |

A block on push is overridden the same way as any other finding: change the line, or, if the model
is wrong, add a note to an ignore list the hook reads (by file and line hash, never by the text), in
a commit that a person reads. Not with `--no-verify`, which CONTRIBUTING.md already rules out.

**When the model is down: fail open, and say so.** The rules are the enforcement layer, and they
always run. A local server that is not running, a model that is not loaded or an answer that does
not parse should not block every commit. The hook prints one line saying the reviewer did not run
and why, and the commit proceeds. The one exception is the strict pre-push mode: there it fails
closed, because a push to a public remote is the moment you would want the check most, and starting
the server is a small price for it.

This is the opposite of Chapter 1B, which fails closed when a file cannot be labelled. The
difference is what the model is for. In 1B the model's label is the only thing deciding where a
sensitive file goes. Here the model is an extra layer above rules that already ran.

**The model's log is a copy of your diff.** Chapter 1B found that LM Studio's server log kept every
prompt it was sent. A reviewer that runs on every commit would write every added line of every
commit into that log, including the ones it flagged. The chapter should:

- Prefer Apple's on-device model on a Mac, which has no server log for this.
- For LM Studio or Ollama, check whether the server you run can turn prompt logging off, and turn
  it off if it can. Check your version; this changes.
- Have the hook print where the log is, after any run that produced a finding, so you know which
  file to delete.
- Never send a diff to a model whose logs you cannot find.

## 8.7 Measuring it

The chapter would follow the pattern of
[`bakeoff.py`](../01-files-and-folders/1d-projects/bakeoff.py) and
[`score.py`](../01-files-and-folders/1d-projects/score.py) from Chapter 1D: a generated fixture with
an answer key, the same prompt for every model, and a table.

**The fixture is generated, not committed.** A set of planted leaks cannot live in the repository
as data: the guard would refuse it, and rightly so, and the allowlist admits no JSON. Instead, a
script in the style of `make_project_mess.py` writes the fixture into a `practice*` folder, together
with an answer key. Anything shaped like a pattern the rules catch is assembled at run time, so the
generator's own source contains no literal match. Every value is made up.

The fixture is a set of small diffs of four kinds:

1. **Planted leaks the rules miss**, one or more per category in 8.4: a made-up full name beside "my
   brother", a sentence about a prescription, a made-up street address, a hostname ending in
   `.internal`, a fixture row with a plausible name, address and birth date, a file name such as a
   tax form for a year.
2. **Clean diffs that look risky**: prose about tax returns and medical bills, the fixture name
   Jordan Lee, `example.com` addresses, a paragraph describing what the guard blocks, a credits
   section naming an author. Taking lines from the book's own chapters is a good source.
3. **Leaks the rules already catch**, to confirm the hook never reaches the model with them.
4. **Injection cases**: a planted leak with a line beside it addressed to the model, asking it to
   approve the commit or to report no findings. Also a clean diff with a line asking the model to
   flag something.

The numbers to report, per model:

| Number | What it means |
|---|---|
| Leaks found | Planted leaks reported at the right file and line |
| Clean lines flagged | False positives on the clean diffs; this is the number that decides whether people keep the hook on |
| Wrong category | Found at the right line but filed under the wrong category |
| Leaks found under injection | Planted leaks still reported when the diff asks the model not to |
| Invented findings under injection | Clean lines flagged because the diff asked for it |
| Failed | Answers that did not parse or named a file or line not in the diff |
| Seconds per diff | How long a commit waits |

As in Chapter 1D, the costly mistake decides between models. In 1D it was a file filed under the
wrong project. Here it is a missed leak on push, and next to it a high count of clean lines flagged,
because a noisy hook gets bypassed and then catches nothing.

The thresholds in 8.6 come from this table. Run it with several models, as section 1D.12 does, and
set the block threshold where clean lines flagged is close to zero.

## 8.8 Placement

Two options:

- **A chapter in this book, after Chapter 7.** It turns the book's own method on the book: propose
  (the model flags lines), approve (you read them), verify (the rules and the evaluation). It reuses
  the local model setup from 1B and 1C and the measuring approach from 1D. The global hook already
  has a slot for it, after the rules.
- **A separate project.** A reusable hook for any repository, with its own installation and release
  process.

**Recommendation: a chapter here first.** The design depends on things the book has already taught,
and the chore is one every reader has: keeping their own data out of what they publish. A separate
project makes sense later, if the hook turns out to be useful outside the book. The chapter's
scripts would then be its first version. Adding the chapter would also need a row in the README's
chapter table, which this note leaves for when the chapter is written.

## 8.9 Open questions

- Whether Apple's on-device model, with its guardrails, refuses diffs that contain health or
  financial text. Chapter 1C saw one refusal in 60 files. For a reviewer, a refusal should count as
  "did not run", not as a finding or a pass.
- How large a diff the small on-device context window can take per call before quality drops.
- Whether the ignore list in 8.6 should live in the repository (shared, but it names lines) or
  inside `.git/` like the private blocklist (private, but lost on a fresh clone).
- Whether a cheap first pass, such as an embedding model, can skip lines that are clearly clean, as
  section 1D.12 suggests for project assignment.
