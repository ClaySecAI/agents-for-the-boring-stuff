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

## 9B.4 Making it take effect

A hook starts working at the next session start. To refresh:

- **Claude app (Code tab):** start a new session.
- **CLI:** exit and run `claude` again, or run `/clear`, which also starts a fresh session and fires the hook.
- **After you edit `settings.json`:** open a new session, or check `/hooks` in the CLI to confirm the hook is listed.

The first line the hook prints is your proof it ran. If you see no `skillgate:` line, the hook is not firing: check that
`.claude/settings.json` has the `hooks` entry and that you opened the session in this project folder, because
`$CLAUDE_PROJECT_DIR` is the folder you opened.

Check the last line `adopt` prints: `recorded in …/released.json`. It should be your real state folder (section 9.7). If it
points somewhere in `/tmp`, an earlier experiment left `SKILLGATE_HOME` set in that terminal. Run `unset SKILLGATE_HOME` or
open a fresh terminal, and adopt again. We did exactly this by accident while writing the chapter: six adoptions went to a
temporary folder and the hook still said "not vetted."

## 9B.5 After you edit something you adopted

You will change your own skills and agents. The next session the hook says CHANGED, which is the hook doing its job.
Read what you changed, then adopt it again (adopting a path that is already recorded replaces its hash):

```bash
python3 chapters/09-skill-security/skillgate.py adopt .claude/agents/file-organizer.md --yes
```

If you did not make the change, do not adopt it. Compare it with your last commit (`git diff`) first.

## 9B.6 What the hook does not do

- It detects and does not block. A skill you drop into `.claude/skills` is usable immediately. The hook tells you at the
  next session start. It cannot stop a download from executing.
- It runs at session start only. A change in the middle of a session shows up next time.
- It does not read the skills. It compares hashes. A skill that was bad when you adopted it stays "ok."
- It skips the app's synced skills. The Claude app keeps its own bundle in `~/.claude/skills/synced` and rewrites it
  on sync. On our machine that bundle alone scanned with 12 high findings (text that quotes attack phrases, and bundled
  archives). The hook says it is not auditing them, rather than hiding that.
- Changing hooks mid-session needs a restart, or a review in the hooks menu, before they apply.

## 9B.7 A step further: asking before anything is written

A stronger layer would use a `PreToolUse` hook: before the agent writes or edits anything under `.claude/skills`,
`.claude/agents` or `settings.json`, Claude Code asks you. That blocks the quiet version of the attack, an agent adding
instructions to itself. We have not built it, because it also interrupts honest edits, the way it would while writing this
book. Whether it is worth that friction depends on what you let agents do while you are away. Chapter 7 returns to this.

## What we tested

`test_skillgate.py` covers the hook's output and logic: the counts it reports, the warning for an item that is not vetted, no
warning once an item is adopted, the CHANGED status after an edit, and that it never exits with an error. It also covers `adopt`
(refusing without `--yes`, refusing a high finding, accepting a risk) and `audit`. On this repository the hook ran from the command
line and reported six items as not vetted before we adopted them.

Not tested: the MISSING status; the hook firing automatically at the start of a real Claude Code session (we ran the command, and
wired it into `settings.json`, but did not watch a fresh session print the line); and how the line looks in the CLI as opposed to the
app.

## Common tasks

Run from the repository root.

| I want to... | Run | How often |
|---|---|---|
| Trust the skills and agents I have | `python3 chapters/09-skill-security/skillgate.py adopt <paths> --yes` | Once per setup |
| Re-trust something I edited | The same `adopt` command, after reading the change | Each edit |
| See what the hook found | `python3 chapters/09-skill-security/skillgate.py audit --target .claude/skills` | When the hook warns |
| Make a new hook take effect | Start a new session, or `/clear` in the CLI | After editing `settings.json` |
| Find where it recorded things | The last line `adopt` prints | If the hook says "not vetted" |

## Exercises

1. Start a new session. Read the one line the hook prints. Does it match what `skillgate.py audit` says?
2. Copy one of your skills into a scratch folder under `.claude/skills`, adopt the copy, change one word in it, and start another session. What does the hook say?
3. Run `adopt` on the scratch copy without `--yes`. What does it tell you? Then delete the copy and see what the hook says.
