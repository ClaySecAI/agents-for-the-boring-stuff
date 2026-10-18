# House style

Every piece of prose in this book goes through the editorial pass before it is committed: the style linter,
the avoid-ai-writing skill in edit mode, and the checklist below. The `editor` agent runs all three.

## Voice

- Short sections, one idea each. Lead with the answer or the command. A reader with a short attention span is the
  reader we write for.
- Say what was tested and what was not. "We ran it" and "we expect" are different sentences.
- Write the how-to as if nothing is installed. Show the command, say what it prints, say what to do if it does not.
- Credit the human and the agent honestly. This book is built with an AI assistant, and says so.

## Chicago conventions we apply

- Serial (Oxford) comma: "files, folders, and links."
- Spell out one through nine in prose; numerals for sizes, ports, versions, counts in tables and code ("24 GB",
  "port 1234", "59 files").
- "percent" in prose; "%" in tables and code.
- Headings in sentence case, for consistency with the rest of the repository.
- Straight quotes in markdown and code. Italics for a term on first use. No bold lead-ins at the start of paragraphs.
- No em dashes. Use a comma, a period, or parentheses.
- Spell out abbreviations on first use.
- American English throughout: "labeled", "neighbor", "color", "organize", "gray", "judgment". The linter flags the British forms.

## AI patterns we remove

<!-- style:off -->
The full list is in the avoid-ai-writing skill. The ones we hit most: inflated words (robust, comprehensive, seamless,
leverage), hollow intensifiers (genuinely, truly), filler openers (it is worth noting), "not X but Y" reveals,
bold-label bullets with periods, and rule-of-three padding.
<!-- style:on -->

## Chapter shape

Every chapter README, and every sub-chapter README (1B, 9C, and so on), has these sections in this order. The linter requires the
last four by name.

1. One paragraph: what this chapter does and why.
2. Numbered sections, each short. Sub-chapters number as `1D.3`.
3. **Limits**: what the approach cannot do or gets wrong.
4. **What we tested**: three parts, in this order.
   - *Tested:* what ran, on what, how many times, with the numbers.
   - *Not tested:* what a reader might assume we checked and we did not (other platforms, other models, the real scheduler, real
     data). Say "none" only if that is true.
   - *How much to trust it:* one sentence. A single run is an anecdote, not a measurement.
5. **Common tasks**: a table of task, command, how often.
6. **Exercises** that use practice data, never the reader's real files.

A setup or concept page with nothing to run still has a "What we tested" section. It says what was not run.

## Safety in examples

- No real file names, folder names, project names, account numbers, or people from anyone's machine. Invent them.
- Commands are copy-and-paste. One command per code block.
- Tokens and secrets never appear, even as examples.

## Tools the editorial pass uses

- **avoid-ai-writing**, by Conor Bronsdon (MIT): [github.com/conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing).
  The author of this book contributed to its style guidance. We vendor the skill (`SKILL.md`, `references/patterns.md`, and the license) at
  v3.38.0, commit `0a4f1ad`, in `.claude/skills/avoid-ai-writing`. It came in through this book's own skill gate (Chapter 9): quarantined,
  scanned, reviewed, and released by a person, with two scanner findings accepted and their reason on record.
- **`scripts/style_check.py`**: the deterministic half. Same text in, same findings out.
- **The `editor` agent** runs both, then checks consistency against this guide.
