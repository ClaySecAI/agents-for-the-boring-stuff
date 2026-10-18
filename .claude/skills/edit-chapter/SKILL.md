---
name: edit-chapter
description: Run the editorial pass on book prose before committing it: style linter, avoid-ai-writing, house-style checklist. Use whenever chapter text, a README or any doc changes.
---

# Edit a chapter

1. Name the file or folder. Ask only if it is unclear.
2. Call the `editor` agent on it.
3. Run `python3 scripts/style_check.py <path> --chapters` yourself and show the finding count.
4. Report in a few lines: changes made, anything left and why, and any decision the author needs to make.

Do not commit text that has not been through this pass. The pre-commit guard checks privacy; this pass checks style. They are
separate on purpose.
