# Backlog

What is left to do, in the order we would do it. The state of each chapter is in its `TESTED.md`. How to pick the work up is
in [HANDOFF.md](HANDOFF.md).

## Next

1. Vet the project's own skills and agents through the skill gate. At session start the gate reported ten items that never went through
   it: five skills in `.claude/skills`, four agents in `.claude/agents`, and the `session-start-hook` skill. We wrote them, but
   "we wrote it" is not a record. Run `vet-skill` on each. A person runs `skillgate.py release` or `adopt`; `.claude/settings.json`
   denies Claude those two commands on purpose.
2. Register the `file-organizer` agent. Start Claude Code with the repository folder as the working directory, then run `/agents`
   and check that `file-organizer` (model: haiku) is listed. Then ask it to tidy the practice folder from `make_mess.py`.
3. Run the editorial pass (`edit-chapter`) on any chapter prose changed since the last pass, before the next commit.

## Chapters not written yet

| Chapter | What exists | What is missing |
|---|---|---|
| 07 Scheduling | `source-notes.md` | The chapter and its `TESTED.md`. Chapter 1E covers one scheduled job; 07 should generalize it. |
| 08 Security reviewer | `PLAN.md` | The chapter, any scripts, and `TESTED.md` |
| 10 Editor | `source-notes.md` | The chapter and `TESTED.md`. The `editor` agent and `edit-chapter` skill already exist. |
| 11 Securing git | `OUTLINE.md` | The chapter, any scripts, and `TESTED.md` |

## Known gaps in chapter 1

These come from the Not tested list in `chapters/01-files-and-folders/TESTED.md`.

- Windows and Linux. All tests ran on macOS. The Finder `.DS_Store` handling is Mac-specific.
- A disk that tells `A.txt` and `a.txt` apart.
- Sonnet and Opus. The model table in section 1.5 is advice, not a measurement.
- Whether two runs of the same model produce the same plan.
- Whether a plan is a good plan. The verifier proves that nothing was lost, not that the folders make sense.

## Later

- Run the undo script against a plan from a real folder (not only throwaway folders) and record the result in `TESTED.md`.
- Set up the project's own SessionStart hook for cloud sessions so tests run there without manual steps (the
  `session-start-hook` skill covers this, and chapter 9B teaches it).
