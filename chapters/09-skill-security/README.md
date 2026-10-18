# Chapter 9: Vetting skills before you install them

A skill is text and scripts that an agent follows with your permissions. A downloaded skill can read your
files, run commands, and change your agent's own settings, and it arrives looking like a README. This
chapter builds a gate: nothing installs until it has been scanned by rules, reviewed by an agent, and
released by you.

[Chapter 9B](9b-session-hook/README.md) makes the gate check
automatically every time you start a session. [Chapter 9C](9c-agents/README.md) covers agents, which are single files
and needed their own handling.

## 9.1 Why two reviewers

| | Deterministic scan | Reviewer agent |
|---|---|---|
| Same input, same answer | Yes | No |
| Finds a known bad pattern | Reliably | Usually |
| Notices a skill whose behavior does not match its purpose | No | Yes |
| Can be talked out of a finding | No | Yes, by text inside the skill |
| Can invent evidence | No | Yes |

Each covers the other's weakness. The scan is blind to intent. The reviewer understands intent but can be
fooled, so a script checks every quote it cites. You make the final call.

A skill raises three different questions, and no one tool answers all of them:

| Question | Best answered by |
|---|---|
| Is there known malware in these files? | VirusTotal hash lookup |
| Does the code or text contain dangerous patterns? | Our rules and SkillSpector |
| Does it do what it says it does, and could that cause harm? | The reviewer agent |

Most skill problems are the second and third kind: instructions that do not match the stated purpose, or a script
that quietly reads a secret. Those have no signature to look up. A hash lookup rounds out the set by catching the
first kind, a known-bad binary or script, and it sends only file hashes.

## 9.2 The flow

```
downloaded skill --> quarantine --> scan ----------+
                     (read-only     (rules, plus   |
                      copy, never    SkillSpector) +--> decide --> you release (--yes)
                      run)         reviewer agent--+                  |
                                    + quote check                     v
                                                              installed, hash recorded
```

- **Quarantine:** `skillgate.py quarantine <folder>` copies the skill into a holding area, removes execute
  permission, and records where it came from. Nothing in it is ever run.
- **Scan:** our rules, plus any outside scanners you have installed (section 9.3). Each scanner is an adapter that
  reports whether it ran, whether it sends anything off your machine, and how many high findings it has.
- **Review:** the `skill-reviewer` agent can only read files. It answers "would this cause harm?" as JSON, and
  every claim carries an exact quote.
- **Verify:** `verify-review` searches each quote in the file it names. An invented quote fails.
- **Decide:** `blocked` (any high finding, or a block verdict), `needs-human`, or `release-candidate`. A skill is a
  `release-candidate` only when the reviewer allows it with quotes that verify (an `allow` with no quotes needs a
  human) and a local outside scanner such as SkillSpector ran. Without one installed, the best a skill gets is
  `needs-human`.
- **Release:** you run it, with `--yes`. It copies the skill to your skills folder, records its hash, and refuses
  to overwrite anything. A blocked skill needs `--accept-risk "reason"`, which is logged.
- **Audit:** `skillgate.py audit --target <skills folder>` flags a released skill that changed since release,
  and any skill that never went through the gate.

## 9.3 The scanners

`skillgate.py` needs only Python 3.9. Outside scanners add independent opinions. They differ in what leaves your
machine, so the gate treats them differently.

| Scanner | Runs where | What it sends | When it runs |
|---|---|---|---|
| Our rules | Local | Nothing | Always |
| [NVIDIA SkillSpector](https://docs.nvidia.com/skills/scanning-agent-skills) | Local, static pass only (`--no-llm`) | Nothing | Whenever it is installed |
| [Snyk agent-scan](https://github.com/snyk/agent-scan) | Snyk's service | The skill's content, secrets redacted | Only with `--remote`; needs `SNYK_TOKEN`. **Optional and unsupported:** see below |
| [VirusTotal](https://ai.virustotal.com) | VirusTotal's service | File hashes only, never content | Only with `--vt`; needs an Agent Token (below) |

Use the remote ones on skills you downloaded from a public place, where the content is already public. Do not send a
skill you wrote for your own private work. VirusTotal says its normal uploads are shared with the security community,
so the gate never uploads; it looks files up by hash. A file VirusTotal has never seen is "unknown", and a clean result
is not proof of safety.

Snyk agent-scan is optional, and we cannot support it. With a valid token (Snyk's API returned 200 for it) and a plan
that shows 200 tests a month, every scan came back "Daily usage limit reached for the public version of Agent-Scan"
(HTTP 429), on several tries over days. We could not find out why, so we never saw a real finding from it. The gate
treats an error as "did not run", never clean. If you have a Snyk plan where it works, the adapter is there, and a
report that works would let us finish the parser.

VirusTotal needs no account. Its Agent Token comes from one anonymous request. This keeps the token in a shell
variable and prints only its length:

```bash
VT_AGENT_TOKEN=$(curl -s -X POST https://ai.virustotal.com/api/v3/agents/register -H "Content-Type: application/json" -d '{"agent_family":"custom","agent_version":"1"}' | python3 -c "import sys,json;print(json.load(sys.stdin)['agent_token'])"); export VT_AGENT_TOKEN; echo "length: ${#VT_AGENT_TOKEN}"
```

To keep it between sessions, save it the way VirusTotal's guide does, in a file only you can read
(`~/.config/vtai/auth.header`, mode 0600, one line: `Authorization: Bearer <token>`); `skillgate.py` reads that file when
`VT_AGENT_TOKEN` is not set. Limits: 60 queries a minute and 1,000 a day, so the gate looks up at most 20 files per skill.
A hash VirusTotal has never seen returns 404, which most new skills will, and means nothing about safety.

Install SkillSpector. It is code too; read what you install. Without it, or another local scanner, no skill reaches
`release-candidate` (9.2).

Its setup uses `uv`, a Python package manager. Check whether you have it:

```bash
uv --version
```

If that says "command not found", install it with Homebrew:

```bash
brew install uv
```

Without Homebrew, or on Linux, follow the install guide at [docs.astral.sh/uv](https://docs.astral.sh/uv/). Then clone
SkillSpector into the folder the gate checks by default:

```bash
git clone https://github.com/NVIDIA/SkillSpector.git ~/.local/share/skillgate-tools/SkillSpector
```

Set it up. SkillSpector needs Python 3.12 to 3.14, and `uv sync` fetches one if you do not have it:

```bash
cd ~/.local/share/skillgate-tools/SkillSpector && uv sync
```

Check that it runs:

```bash
~/.local/share/skillgate-tools/SkillSpector/.venv/bin/skillspector --version
```

The gate looks in four places, in order: the `--skillspector` flag, your PATH, a `"skillspector"` entry in `config.json`
inside the gate's state folder, and `~/.local/share/skillgate-tools/SkillSpector/.venv/bin/skillspector`. If you cloned it
where the commands above put it, there is nothing to register. If you put it somewhere else, write its full path into the
config file (`~/.local/state/skillgate/config.json` on Linux, `~/Library/Application Support/skillgate/config.json` on a
Mac): `{"skillspector": "/full/path/to/skillspector"}`. Then `skillgate.py scan` shows "skillspector ran (local)".

For Snyk, install a pinned version, not `@latest` (v0.6.8 was current in October 2026):

```bash
uv tool install snyk-agent-scan==0.6.8
```

Then `skillgate.py` finds `snyk-agent-scan` on your PATH. Without installing, pass `--agent-scan "uvx snyk-agent-scan@0.6.8"`. You need a Snyk account and token; the book cannot create one for you.

## 9.4 Vetting a skill

```bash
python3 chapters/09-skill-security/skillgate.py quarantine ~/Downloads/some-skill --origin "where I found it"
python3 chapters/09-skill-security/skillgate.py scan <id>                   # local scanners only
python3 chapters/09-skill-security/skillgate.py scan <id> --vt --remote     # also VirusTotal hashes and Snyk
```

Then ask your agent to review it, or invoke the flow directly with the `vet-skill` skill. It calls the reviewer
and saves its reply:

```bash
python3 chapters/09-skill-security/skillgate.py verify-review <id> review.json
python3 chapters/09-skill-security/skillgate.py decide <id>
```

Read the reasons. If you agree, release it:

```bash
python3 chapters/09-skill-security/skillgate.py release <id> --target .claude/skills --yes
```

Run it yourself, in your terminal. The repository's `.claude/settings.json` has deny rules for `skillgate.py release`
and `adopt`, but treat them as a speed bump. They match only commands that begin with `python3 ` or `python `. An agent
that types `/usr/bin/python3 …`, calls the script from a shell script, or runs it through `python3 -c` and `runpy` gets
past them, and an agent allowed to edit files can change `released.json` directly. Section 9B.7 describes the stronger
layer, a hook that asks you before a write, and why we have not built it.

## 9.5 What the rules look for

High: pipe-to-shell (`curl … | sh`), decoding and running, reading `~/.ssh` and other credential stores, writing
to agent settings, hooks, or shell profiles, persistence (cron, launchd), text telling the agent to hide things
from you or ignore its instructions, hooks, invisible characters, links that point outside the skill, opaque
binaries, and any file that reads a secret and also makes network calls. Medium: broad tool grants, shell
injection risks, network calls (unless every address on the line is your own machine; a comment that mentions
localhost does not count), destructive commands, secret-looking environment reads. Low: scripts, hidden files,
executable bits, installs.

A finding is evidence, not a verdict. Our own skills scan with no high findings, and one false positive (a
`curl` to localhost) led to a fix.

## 9.6 What the gate touches

A tool that guards your machine should be easy to inspect. This is everything `skillgate.py` does.

| What | Where | Notes |
|---|---|---|
| Quarantined copies | `<state>/quarantine/<id>/` | Read-only, no execute bit, never run |
| Per-skill record | `<state>/meta/<id>.json` | Scan results, reviewer verdict, state |
| Scanner reports | `<state>/meta/<id>.reports/` | Raw SkillSpector output, and others if you ran them |
| What you released or adopted | `<state>/released.json` | Path and hash of each trusted item |
| History | `<state>/audit.log` | One line per action; read it with `cat` |
| Scanner install | `~/.local/share/skillgate-tools/` | Only if you followed 9.3 |

`<state>` is `~/.local/state/skillgate` on Linux and `~/Library/Application Support/skillgate` on a Mac. Override it with
`SKILLGATE_HOME`.

- Network: none by default. SkillSpector runs with `--no-llm`. Snyk needs `--remote` and VirusTotal needs `--vt`, and
  VirusTotal gets hashes only.
- No background process: it runs when you run it, or when the hook in 9B fires at session start.
- It never edits your skills. It copies them in, and only `release` or `adopt` (a person, with `--yes`) records
  anything as trusted. `forget` (also `--yes`) removes the record of an item you deleted on purpose.
- To remove it, delete `<state>` and the `hooks` entry in `.claude/settings.json`. Nothing else was changed.

To see exactly what happened, read the log:

```bash
cat ~/.local/state/skillgate/audit.log     # or the Mac path above
```

## 9.7 Limits

- A skill can be harmful in ways no rule names and a reviewer misses. The gate lowers the risk; it does not remove
  it. Read the skill yourself before you release one that matters.
- The reviewer is a model: it can be wrong or be steered. That is why it cannot release anything, and why a
  script checks its evidence.
- The deny rules on `release` and `adopt` stop only the plain `python3 …` command (9.4), and `forget` has none (9B.5).
  Run all three yourself.
- Released skills can change on disk. `audit` finds that; run it on a schedule (Chapter 7).
- Agents and slash commands are text with the same powers. Run the same flow on them.

What we tested, and what we did not: [TESTED.md](TESTED.md).

## Common tasks

Run from the repository root.

| I want to... | Run | How often |
|---|---|---|
| Quarantine a skill I downloaded | `python3 chapters/09-skill-security/skillgate.py quarantine <folder> --origin "<where>"` | Each download |
| Scan it | `python3 chapters/09-skill-security/skillgate.py scan <id>` | Each download |
| Check the reviewer's quotes | `python3 chapters/09-skill-security/skillgate.py verify-review <id> <review.json>` | Each download |
| See the decision and its reasons | `python3 chapters/09-skill-security/skillgate.py decide <id>` | Each download |
| Release it, after reading the reasons | `python3 chapters/09-skill-security/skillgate.py release <id> --target .claude/skills --yes` | You, not an agent |
| Vet an agent I downloaded | The same commands, with the `.md` file (9C) | Each download |
| Trust skills and agents I already have | `python3 chapters/09-skill-security/skillgate.py adopt <paths> --yes` (9B.3) | Once per setup |
| Re-trust something I edited | The same `adopt` command, after reading the change (9B.5) | Each edit |
| Clear something I deleted on purpose | `python3 chapters/09-skill-security/skillgate.py forget <path> --yes` (9B.5) | When the hook says missing |
| See if anything changed | `python3 chapters/09-skill-security/skillgate.py audit --target .claude/skills` | When the hook warns |
| Look at the history | `cat` the `audit.log` (9.6) | When curious |
| Add a scanner | Section 9.3 | Once |
| Stop using it | Delete the state folder and the `hooks` entry (9.6) | Rarely |

`release`, `adopt`, and `forget` are yours to run. The repository's deny rules cover only the first two, and only
commands that begin with `python3 ` or `python ` (9.4).

## Exercises

Do these against a practice state folder and a practice skills folder, so nothing touches your real gate. Start with:

```bash
export SKILLGATE_HOME=<practice>/gate
```

1. Build the trap: a skill folder with a `SKILL.md` that says "ignore previous instructions" and a script that reads an environment variable called `API_KEY` and fetches a web address with it. Quarantine it and scan it. Which rules fire?
2. Quarantine and scan your own `organize-folder` skill. Quarantine only copies it, so the original is untouched. What does it find?
3. Add a line to a copy of a skill that tells the reader to ignore its instructions. Which catches it, the scan or the reviewer agent?
4. Release a skill with `--target <practice>/skills`, edit one word in the released copy, and run `audit --target <practice>/skills`.
5. Make a skill folder holding the EICAR test string (look it up; it is a harmless standard file) and scan it with `--vt`. Which scanners flag it, and which do not?

When you finish, so the next real `adopt` does not land in the practice folder (9B.4):

```bash
unset SKILLGATE_HOME
```
