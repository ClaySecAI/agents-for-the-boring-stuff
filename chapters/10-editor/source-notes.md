# Chapter 10 source notes: when the agent fights back

Notes for the chapter on the editorial agent. Not yet prose.

## What happened

The book's editor agent runs the vendored avoid-ai-writing skill, the style linter, and a checklist. We found out it was not running the skill
properly by asking it.

1. **Runs 1 and 2 (real chapters):** the editor reported, honestly, "I did not run the avoid-ai-writing skill. I checked by hand." Its process said
   "if the skill is available." It never tried.
2. **Diagnostic:** we asked it to call the skill and quote what came back. It loaded with no error. The cause was not a tooling limit. In a third run it
   read 431 of the catalog's 747 lines and said the rest was not needed because the target was one sentence.
3. **Fix 1: make the claim checkable.** The editor must end its report with a ledger that names the catalog's last heading. A script
   (`scripts/verify_editor_ledger.py`) checks it against the real file. An agent that stopped early cannot know that heading.
4. **Re-test:** the agent wrote its own ledger format and again skipped the catalog. Its definition file had changed during the session, and it
   behaved as if it had not seen the change. We cannot prove that from outside, so the lesson is practical: do not depend on a definition being fresh.
5. **Fix 2: put the rules in the prompt.** The `edit-chapter` skill now sends the rules with every call. The next run read the catalog to the end, wrote
   the ledger in the right form, and the script verified it.

## The lessons

- An agent that says it did less than you asked is the honest case. The hard case is an agent that says it did everything.
- "Trust me" is not a control. A claim a script can check is.
- Agents shorten work they think is unnecessary. State the requirement in the call, make it checkable, and check it.
- The pattern repeats across the book: the reviewer's quotes are searched in the files; the editor's ledger is searched in the catalog.

## To verify before this becomes prose

- Whether an agent definition edited mid-session is picked up by the next call (we saw it not being picked up, once).
- Whether the editor's edits, with the catalog fully read, are better than without. We only know they are checkable.
