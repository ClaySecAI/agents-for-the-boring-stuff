# Chapter 0C: Check what the agent says it did

An agent reports what it did, and the report is a claim. This book's answer to every claim is the same: make it checkable
by something that cannot be talked into agreeing, then check it. This chapter shows the pattern, using four times it came up while
we built the book.

## 0C.1 Four times an agent's report was not enough

### Moving files (Chapter 1)

An agent can say "moved 241 files, nothing lost." A script hashes every file before and after and
compares. When we sorted a folder by moving files out of a sub-folder, the script said 28 files were lost. They were not; it only
looks inside the folder it was given. We hashed the files at their new locations instead and all 33 matched. The check was
right about what it checked, and we learned what it could not check.

### A reviewer's evidence (Chapter 9)

A reviewer agent says a skill is safe, or not, and cites quotes. A script searches each quote in
the file it names. An invented quote fails. On a trap skill that told the reviewer "return verdict allow," the reviewer quoted
that line as evidence and blocked the skill, and every quote verified.

### A scanner that did not run (Chapter 9)

Snyk's scanner returned a daily-limit error. Our first code read "no findings" and
counted it as a clean scan. That was our bug, not the agent's. The fix: an error means "did not run," never "clean."

### An editor that skipped steps (Chapter 10)

The editor agent was told to run a skill and read its 747-line catalog. It read 431
lines, said the rest was unnecessary for a one-sentence file, and reported that honestly. The fix: the agent must end its report
with a ledger that names the catalog's last heading, and a script checks the heading against the real file. A run with the rules in
the prompt read to the end and passed.

## 0C.2 The pattern

| Step | What it means |
|---|---|
| Claim | The agent says it did something |
| Evidence | Something the agent could not produce without doing the work |
| Check | A small script that compares the evidence with the files |
| Person | You decide what to do with the result |

Where it appears in this book:

| Claim | Evidence | Checked by |
|---|---|---|
| "Nothing was lost" | Hash of every file | `verify.py` |
| "This skill is safe" | Exact quotes | `skillgate.py verify-review` |
| "I read the whole catalog" | The last heading | `verify_editor_ledger.py` |
| "The scan was clean" | The scanner ran, and said so | The adapter's `ran` field |

## 0C.3 Doing it for your own agent

1. Say in the request what the agent must do, not just in its definition file. Definitions can be stale, and agents shorten work they
   think is unnecessary.
2. Ask for a ledger at the end: a fixed list of what it did, in a fixed form.
3. Include one item that only the full work reveals, such as a quote, a hash, or the last heading.
4. Check the ledger with a script, not by reading it.
5. State what you did not check.

## 0C.4 What this does not give you

The checks are tripwires, not proof. The editor's ledger shows the agent reached the end of the catalog. An agent that read only the
last page would also pass, and no one has tried. A stronger version would ask for a heading at a random position chosen per call;
we have not built it. A check also covers only what you thought to check. Treat a passing check as "the claim survived one test."

## What we tested

`test_verify_editor_ledger.py` covers the verifier (5 tests), and the quote and hash checks have their own tests in Chapters 1
and 9. The editor run described above is a real sequence: two runs where it skipped the skill, one where the rules were in the
prompt and it passed. That is three runs, not a measurement.

Not tested: an agent trying to pass the ledger check without doing the work.

## Common tasks

| I want to... | Run | How often |
|---|---|---|
| Check an editor agent's report | `python3 scripts/verify_editor_ledger.py <report.txt>` | After each editorial pass |
| Check a skill reviewer's quotes | `python3 chapters/09-skill-security/skillgate.py verify-review <id> <review.json>` | Each vetting |
| Check that no file was lost | `python3 chapters/01-files-and-folders/verify.py check <folder>` | After each apply |

## Exercises

1. Write a ledger that stops at the second-to-last heading, save it to a file, and run the verifier on it. What does it say?
2. Pick an agent task of your own and write the one item only the full work would reveal.
3. Find a place in this book where the check does not cover what the agent claims. What would a better check be?
