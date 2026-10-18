---
name: edit-chapter
description: Run the editorial pass on book prose before committing it: style linter, avoid-ai-writing, house-style checklist. Use whenever chapter text, a README or any doc changes.
---

# Edit a chapter

1. Name the file or folder. Ask only if it is unclear.
2. Call the `editor` agent on it with this prompt, filling in the path. Put the rules in the prompt: an agent's own definition may
   be stale, and agents shorten work they think is unnecessary.

   > Edit <path> in place. Follow STYLE.md, including American spelling and the Chapter shape sections (report missing ones; never write TESTED.md, the author supplies the facts). Before editing, call the Skill tool with `avoid-ai-writing`, then read
   > `.claude/skills/avoid-ai-writing/references/patterns.md` in full, in pages, to its last heading. Do this even if the target
   > is short. End your reply with this ledger, filled in: a line `Ledger`, then `Skill loaded: yes`, `Catalog read through: <text of
   > the last heading you read>`, `Linter findings: <before> -> <after>`, `Editing passes: <n>`, `Model-only checks: <list>`.
3. Save the editor's whole reply to a file and run `python3 scripts/verify_editor_ledger.py <file>`. It checks that the editor
   loaded the skill and read the catalog to the end. If it fails, send the editor back with the failure and do not accept the pass.
4. Run `python3 scripts/style_check.py <path> --chapters` yourself and show the finding count.
5. Report in a few lines: changes made, anything left and why, and any decision the author needs to make.

Do not commit text that has not been through this pass. The pre-commit guard checks privacy; this pass checks style. They are
separate on purpose.
