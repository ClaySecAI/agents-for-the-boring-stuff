# Chapter 10C: Agents are files, not folders

Chapter 10 vetted skills, which are folders. Agents are different: one markdown file in `.claude/agents/`. The gate's first
version refused them. This chapter covers the gap and how it closed.

## 10C.1 The gap

`skillgate.py quarantine` copied a skill folder. Given an agent, it stopped: "Not a folder." The workaround was to
put the agent file inside a folder. That half worked, and in a way that hid risks:

- The scan complained that there was no `SKILL.md`, which was true and beside the point.
- It never read the agent's own frontmatter, where an agent says what it may do.
- A released agent would have been a folder in `.claude/agents`, which Claude Code does not read.

A skill that is only text can cause harm. An agent also has a tool list, and a missing tool list is itself the finding.

## 10C.2 What an agent can ask for

An agent's frontmatter is its permission slip:

```markdown
---
name: note-tidier
description: Tidies a notes file
tools: Read, Grep
---
```

The gate now reads it and checks:

| Rule | Severity | What it means |
|---|---|---|
| `inherits-all-tools` | medium | No `tools:` line, so the agent gets every tool its parent has. An empty `tools:` line counts the same |
| `broad-tool-grant` | medium | Asks for Bash, Write, Edit, WebFetch or similar |
| `loosens-permissions` | high | Sets a permission mode that skips approvals |
| `defines-mcp-servers` | medium | Brings its own Model Context Protocol (MCP) servers |
| `defines-hooks` | high | Hooks run commands automatically |

The gate reads the common ways of writing frontmatter: a quoted value (`permissionMode: "bypassPermissions"`), a
trailing `# comment`, and a tool list written as `[Read, Bash]` or as one `- Bash` line per tool. It is not a YAML
library (10C.6).

The rules from Chapter 10 still apply to the agent's text: pipe-to-shell, secret reads, "hide this from the user."

## 10C.3 What changed in the gate

`quarantine` accepts a skill folder or an agent `.md` file and records which it is. An agent is copied into a holding folder
alone, read-only. `release` copies the one file into your agents folder and refuses to overwrite. `audit` and the session
hook treat a skills folder as items that are folders, and an agents folder as items that are `.md` files, so an agent that was
never vetted shows as UNGATED, not as a missing skill.

```bash
python3 chapters/10-skill-security/skillgate.py quarantine ~/Downloads/new-agent.md --origin "where I found it"
python3 chapters/10-skill-security/skillgate.py scan <id>
python3 chapters/10-skill-security/skillgate.py release <id> --target .claude/agents --yes     # you, after reading
python3 chapters/10-skill-security/skillgate.py audit --target .claude/agents
```

The reviewer agent works the same way: the quarantine folder holds one file, and its quotes are checked against it.

## 10C.4 What we found when we ran it on our own agents

- `file-organizer` and `project-organizer`: medium, because they may use Bash. That is by design. Look at what they do with it.
- `editor`: medium, because it may use Bash and Edit. It needs them to run the style linter and edit prose in place.
- `skill-reviewer`: a false positive, as in 10B. It lists the places a skill should never read.

## 10C.5 What is still not covered

- **Slash commands** (`.claude/commands/*.md`) are single markdown files with the same powers. The same flow works if you
  pass the file, but the agent-specific rules do not apply.
- **Plugins and MCP servers** bundle code, tools, and hooks. A plugin is closer to a package than a skill; treat it as one.
- **Settings files** (`.claude/settings.json`) can add hooks and permissions. They are not scanned by this gate.

## 10C.6 Limits

Slash commands, plugins, MCP servers, and settings files are not covered by the agent rules or the gate (10C.5). The
frontmatter reader is not a YAML library: multi-line values, anchors, and other YAML beyond `key: value` and simple lists
are not read, so read the frontmatter of any agent you install. Three things are untested: the `defines-mcp-servers` and
`defines-hooks` rules on an agent, slash commands, and plugins.

What we tested, and what we did not: [TESTED.md](TESTED.md).

## Common tasks

Run from the repository root.

| I want to... | Run | How often |
|---|---|---|
| Vet an agent I downloaded | `python3 chapters/10-skill-security/skillgate.py quarantine <agent.md> --origin "<where>"`, then `scan` | Each download |
| Install it after review | `python3 chapters/10-skill-security/skillgate.py release <id> --target .claude/agents --yes` | You, after reading |
| Check my agents for changes | `python3 chapters/10-skill-security/skillgate.py audit --target .claude/agents` | When the hook warns |

## Exercises

Quarantine writes to the gate's state folder, so point it at a practice one first:

```bash
export SKILLGATE_HOME=<practice>/gate
```

1. Copy `.claude/agents/file-organizer.md` to a temporary file, delete its `tools:` line, and scan it. What changes?
2. Add `permissionMode: bypassPermissions` to a copy and scan it. Is the verdict what you expect?
3. Quarantine, review, and release an agent with `--target <practice>/agents`, then change it and run `audit --target <practice>/agents`.

When you finish:

```bash
unset SKILLGATE_HOME
```
