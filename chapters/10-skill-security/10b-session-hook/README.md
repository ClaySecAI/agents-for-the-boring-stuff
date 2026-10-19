# Chapter 10B: Checking automatically at session start

Chapter 10 gives you a gate. A gate you must remember to use gets skipped. This chapter adds a hook that audits your skills
and agents every time you start Claude Code, and tells you in one line what it found.

## 10B.1 What a hook is

A hook is a command that Claude Code runs for you at a fixed moment: a session starting, a tool about to run. You define it in
`.claude/settings.json`. The program, not the model, runs it, so it happens whatever the model decides.

Ours runs at session start. It is in this repository's settings:

```json
"hooks": {
  "SessionStart": [
    {"hooks": [{"type": "command",
                "command": "python3 \"$CLAUDE_PROJECT_DIR\"/chapters/10-skill-security/skillgate.py hook"}]}
  ]
}
```

`$CLAUDE_PROJECT_DIR` is the folder you opened. The hook prints a short JSON message; Claude Code shows the
`systemMessage` to you and gives Claude the `additionalContext` if there are problems.

## 10B.2 What it checks

It looks at four places: `.claude/skills` and `.claude/agents` in the project, and the same two folders in your home
directory. For each skill or agent it compares the current hash with the one recorded when you released or adopted it.

| Status | Meaning |
|---|---|
| ok | Same as when you trusted it |
| CHANGED | The files differ from what you trusted |
| UNGATED | Never went through the gate |
| MISSING | You trusted it, and now it is gone |
| APP-SYNCED | The Claude app's own synced bundle, counted and named but not audited (10B.6) |

You see one line, for example `skillgate: 6 verified, 0 changed, 0 not vetted, 0 missing`. If anything is wrong, Claude is
also told, and the details are one command away: `skillgate.py audit --target .claude/skills`.

A skill or agent can be a link to a folder or file somewhere else, a common way to work on a skill in one place and use it in
another. The hook follows the link, checks what it points to, and names it in the line ("linked from elsewhere"). If the link
is changed to point somewhere else, that item shows CHANGED, even when the new target has the same files.

## 10B.3 Setting your baseline

On a new setup, everything is UNGATED, because nothing has been recorded. For a skill you downloaded, use the full flow in
Chapter 10. For ones you already have or wrote, `adopt` records them as your baseline. It scans them first and refuses
any with high findings unless you accept the risk in writing.

```bash
python3 chapters/10-skill-security/skillgate.py adopt .claude/skills/* .claude/agents/*.md --yes
```

What happened when we did this on this repository's own items:

- The five skills had no high findings. Four scanned clean. `avoid-ai-writing` had one medium note, a false positive: its
  style guide mentions apps that "curl quotes", and the network-call rule read the verb as the `curl` command.
- Three agents (`editor`, `file-organizer`, `project-organizer`) had a medium note: they are allowed to use Bash, which they
  need for their jobs. That does not block adoption.
- The `skill-reviewer` agent was refused: its text mentions reading `~/.ssh`, because it tells the reviewer to look for exactly
  that. A rule cannot tell a description of an attack from the attack. We read the file, saw why, and adopted it with the
  reason on record:

```bash
python3 chapters/10-skill-security/skillgate.py adopt .claude/agents/skill-reviewer.md --yes --accept-risk "describes what to look for"
```

A second refusal came later, and that one was a bug in the gate. We edited our own `edit-chapter` skill to add a prompt template written
as a markdown quote (lines starting with `>`), and `adopt` refused it for writing to the agent's configuration. The rule had read the
`>` quote marker as a shell redirect. We read the finding, saw the cause, fixed the rule, and added a test that a quote marker passes
while a real `echo hi > .claude/skills/...` still fails. A gate that refuses your own work is doing its job, and reading why is how
you find out whether the skill or the rule is wrong.

The `--accept-risk` reason goes into `audit.log`. Both `adopt` and `release` have deny rules in `.claude/settings.json`. They stop the plain
`python3 …` command an agent would usually type, not every way to run the script (10.4), so treat them as a speed bump and run
both yourself.

## 10B.4 Making it take effect

A hook starts working at the next session start. To refresh:

- **Claude app (Code tab):** start a new session.
- **CLI:** exit and run `claude` again, or run `/clear`, which also starts a fresh session and fires the hook.
- **After you edit `settings.json`:** open a new session, or check `/hooks` in the CLI to confirm the hook is listed.

The first line the hook prints is your proof it ran. If you see no `skillgate:` line, the hook is not firing: check that
`.claude/settings.json` has the `hooks` entry and that you opened the session in this project folder, because
`$CLAUDE_PROJECT_DIR` is the folder you opened.

Check the last line `adopt` prints: `recorded in …/released.json`. It should be your real state folder (section 10.6). If it
points somewhere in `/tmp`, an earlier experiment left `SKILLGATE_HOME` set in that terminal. Run `unset SKILLGATE_HOME` or
open a fresh terminal, and adopt again. We did exactly this by accident while writing the chapter: six adoptions went to a
temporary folder and the hook still said "not vetted."

## 10B.5 After you edit or delete something you adopted

You will change your own skills and agents. The next session the hook says CHANGED, which is the hook doing its job.
Read what you changed, then adopt it again (adopting a path that is already recorded replaces its hash):

```bash
python3 chapters/10-skill-security/skillgate.py adopt .claude/agents/file-organizer.md --yes
```

If you did not make the change, do not adopt it. Compare it with your last commit (`git diff`) first.

If you delete something you adopted, the hook says MISSING from then on, because a skill that disappears without your knowing
is also worth a warning. Once you are sure you deleted it on purpose, clear the record:

```bash
python3 chapters/10-skill-security/skillgate.py forget .claude/skills/old-skill --yes
```

`forget` refuses anything that is still on disk. To re-trust an item you changed, adopt it again. Like `adopt`, `forget` is
yours to run; the repository has no deny rule for it yet.

## 10B.6 What the hook does not do

- It detects and does not block. A skill you drop into `.claude/skills` is usable immediately. The hook tells you at the
  next session start. It cannot stop a download from executing.
- It runs at session start only. A change in the middle of a session shows up next time.
- It does not read the skills. It compares hashes. A skill that was bad when you adopted it stays "ok."
- It does not audit the app's synced skills. The Claude app keeps its own bundle in `~/.claude/skills/synced` and rewrites
  it on sync. On our machine that bundle alone scanned with 12 high findings (text that quotes attack phrases, and bundled
  archives). The hook recognizes the bundle by its layout (a manifest listing the skills, and a marker file the app writes
  beside it), not by the folder's name, and its line names the bundle and how many skills it holds. A folder called `synced`
  without that layout is audited like any other. Anything that can write to `~/.claude/skills` can copy the layout, which is
  why the line always names it.
- Changing hooks mid-session needs a restart, or a review in the hooks menu, before they apply.

## 10B.7 A step further: asking before anything is written

A stronger layer would use a `PreToolUse` hook: before the agent writes or edits anything under `.claude/skills`,
`.claude/agents` or `settings.json`, Claude Code asks you. That blocks the quiet version of the attack, an agent adding
instructions to itself. We have not built it, because it also interrupts honest edits, the way it would while writing this
book. Whether it is worth that friction depends on what you let agents do while you are away. Chapter 7 returns to this.

The same hook would be the stronger answer to the deny rules in 10.4. It sees each file write before it happens, so it could ask
before anything writes to the gate's state folder, which a rule about how a command begins cannot do. It cannot see inside a
script that Bash runs, so an agent with unrestricted Bash can still get around both layers.

## 10B.8 Limits

The hook detects and does not block, runs at session start only, compares hashes without reading the skills, and does not
audit the app's synced skills (10B.6). The `PreToolUse` layer that would ask before a write is not built (10B.7). The deny rules
for `adopt` and `release` are a speed bump, and `forget` has none. Untested: how the line looks in the CLI as opposed to the
app. The hook firing on its own in a fresh session was seen once, second-hand.

What we tested, and what we did not: [TESTED.md](TESTED.md).

## Common tasks

Run from the repository root.

| I want to... | Run | How often |
|---|---|---|
| Trust the skills and agents I have | `python3 chapters/10-skill-security/skillgate.py adopt <paths> --yes` | Once per setup |
| Re-trust something I edited | The same `adopt` command, after reading the change | Each edit |
| Clear something I deleted on purpose | `python3 chapters/10-skill-security/skillgate.py forget <path> --yes` | When the hook says missing |
| See what the hook found | `python3 chapters/10-skill-security/skillgate.py audit --target .claude/skills` | When the hook warns |
| Make a new hook take effect | Start a new session, or `/clear` in the CLI | After editing `settings.json` |
| Find where it recorded things | The last line `adopt` prints | If the hook says "not vetted" |

## Exercises

1. Start a new session. Read the one line the hook prints. Does it match what `skillgate.py audit --target .claude/skills` says?

For the next two, use a practice state folder and a practice skills folder, so your real baseline stays as it is. Start with:

```bash
export SKILLGATE_HOME=<practice>/gate
```

2. Copy one of your skills into `<practice>/skills`, adopt the copy, change one word in it, and run `audit --target <practice>/skills`. What does it say?
3. Run `adopt` on the copy without `--yes`. What does it tell you? Then delete the copy, run `audit` again, and clear it with `forget`.

When you finish:

```bash
unset SKILLGATE_HOME
```
