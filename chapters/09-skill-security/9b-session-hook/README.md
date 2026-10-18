# Chapter 9B: Checking automatically at session start

Chapter 9 gives you a gate. A gate you must remember to use gets skipped. This chapter adds a hook that audits your skills
and agents every time you start Claude Code, and tells you in one line what it found.

## 9B.1 What a hook is

A hook is a command that Claude Code runs for you at a fixed moment: a session starting, a tool about to run. You define it in
`.claude/settings.json`. The program, not the model, runs it, so it happens whatever the model decides.

Ours runs at session start. It is in this repository's settings:

```json
"hooks": {
  "SessionStart": [
    {"hooks": [{"type": "command",
                "command": "python3 \"$CLAUDE_PROJECT_DIR\"/chapters/09-skill-security/skillgate.py hook"}]}
  ]
}
```

`$CLAUDE_PROJECT_DIR` is the folder you opened. The hook prints a short JSON message; Claude Code shows the
`systemMessage` to you and gives Claude the `additionalContext` if there are problems.

## 9B.2 What it checks

It looks at four places: `.claude/skills` and `.claude/agents` in the project, and the same two folders in your home
directory. For each skill or agent it compares the current hash with the one recorded when you released or adopted it.

| Status | Meaning |
|---|---|
| ok | Same as when you trusted it |
| CHANGED | The files differ from what you trusted |
| UNGATED | Never went through the gate |
| MISSING | You trusted it, and now it is gone |

You see one line, for example `skillgate: 6 verified, 0 changed, 0 not vetted`. If anything is wrong, Claude is also told,
and the details are one command away: `skillgate.py audit --target .claude/skills`.

## 9B.3 Setting your baseline

On a new setup, everything is UNGATED, because nothing has been recorded. For a skill you downloaded, use the full flow in
Chapter 9. For ones you already have or wrote, `adopt` records them as your baseline. It scans them first and refuses
any with high findings unless you accept the risk in writing.

```bash
python3 chapters/09-skill-security/skillgate.py adopt .claude/skills/* .claude/agents/*.md --yes
```

What happened when we did this on this repository's own items:

- The three skills scanned clean.
- Two agents (`file-organizer`, `project-organizer`) had a medium note: they are allowed to use Bash, which is the point of
  them. That does not block adoption.
- The `skill-reviewer` agent was refused: its text mentions reading `~/.ssh`, because it tells the reviewer to look for exactly
  that. A rule cannot tell a description of an attack from the attack. We read the file, saw why, and adopted it with the
  reason on record:

```bash
python3 chapters/09-skill-security/skillgate.py adopt .claude/agents/skill-reviewer.md --yes --accept-risk "describes what to look for"
```

The reason goes into `audit.log`. Both `adopt` and `release` are denied to agents in `.claude/settings.json`, so only you can run
them.

## 9B.4 What the hook does not do

- **It detects. It does not block.** A skill you drop into `.claude/skills` is usable immediately. The hook tells you at the
  next session start. It cannot stop a download from executing.
- **It runs at session start only.** A change in the middle of a session shows up next time.
- **It does not read the skills.** It compares hashes. A skill that was bad when you adopted it stays "ok."
- **It skips the app's synced skills.** The Claude app keeps its own bundle in `~/.claude/skills/synced` and rewrites it
  on sync. On our machine that bundle alone scanned with 12 high findings (text that quotes attack phrases, and bundled
  archives). The hook says it is not auditing them, rather than hiding that.
- **Changing hooks mid-session** needs a restart, or a review in the hooks menu, before they apply.

## 9B.5 A step further: asking before anything is written

A stronger layer would use a `PreToolUse` hook: before the agent writes or edits anything under `.claude/skills`,
`.claude/agents` or `settings.json`, Claude Code asks you. That blocks the quiet version of the attack, an agent adding
instructions to itself. We have not built it, because it also interrupts honest edits, the way it would while writing this
book. Whether it is worth that friction depends on what you let agents do while you are away. Chapter 7 returns to this.

## Exercises

1. Start a new session. Read the one line the hook prints. Does it match what `skillgate.py audit` says?
2. Change one word in an adopted skill and start another session. What does the hook say?
3. Run `adopt` without `--yes`. What does it tell you?
