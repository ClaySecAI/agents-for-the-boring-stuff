"""A gate between a downloaded skill and your agents. Nothing installs until a person releases it.

    python3 skillgate.py quarantine <skill-folder> [--origin TEXT]   copy it into quarantine, read-only
    python3 skillgate.py scan <id> [--skillspector PATH]             deterministic checks (ours, plus SkillSpector if installed)
    python3 skillgate.py verify-review <id> <review.json>            check the reviewer agent's evidence against the files
    python3 skillgate.py decide <id>                                 combine everything: blocked, needs-human or release-candidate
    python3 skillgate.py release <id> --target DIR --yes [--accept-risk REASON]
    python3 skillgate.py audit --target DIR                          has a released skill changed since release?
    python3 skillgate.py status [<id>]

The flow has three independent opinions. (1) Deterministic rules find what is mechanically suspicious: the same
input always gives the same findings. (2) A reviewer agent, which can only read, judges whether the skill's
behavior matches its stated purpose and could cause harm; it can be wrong or be talked around, so (3) a script
checks that every piece of evidence it cites really exists in the skill. A person makes the last call.

Quarantine files are copied, stripped of execute permission, and never run. State lives in $SKILLGATE_HOME
(default: ~/.local/state/skillgate, or ~/Library/Application Support/skillgate on a Mac).
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SEVERITY = ["low", "medium", "high"]
TEXT_SUFFIXES = {".md", ".txt", ".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".json", ".yml", ".yaml", ".toml", ".swift", ".rb", ".pl", ".cfg", ".ini", ""}
SCRIPT_SUFFIXES = {".py", ".sh", ".bash", ".zsh", ".js", ".ts", ".rb", ".pl", ".swift"}
MAX_BYTES = 1_000_000

# (severity, rule id, pattern). A finding is evidence for the reviewer, not a verdict.
RULES = [
    ("high", "pipe-to-shell", re.compile(r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b")),
    ("high", "decode-and-run", re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba|z)?sh|eval\s*\(\s*(base64|atob|decode)")),
    ("high", "reads-credentials", re.compile(r"(~|\$HOME|/Us" r"ers/[^/\s]+|/ho" r"me/[^/\s]+)/\.(ssh|aws|gnupg|config/gcloud|netrc|docker/config)")),
    ("high", "writes-agent-config", re.compile(r"(>|>>|tee|cp|mv|write|open)[^\n]{0,60}(\.claude/settings|\.claude/agents|\.claude/skills|CLAUDE\.md|\.git/hooks|\.bashrc|\.zshrc|\.profile)")),
    ("high", "persistence", re.compile(r"\b(crontab|launchctl\s+(load|bootstrap)|systemctl\s+enable|LaunchAgents|schtasks)\b")),
    ("high", "hides-from-user", re.compile(r"(do not|don't|never)\s+(tell|show|mention|reveal|inform)[^\n]{0,40}(user|human)|without\s+(telling|informing|asking)\s+the\s+user", re.I)),
    ("high", "overrides-instructions", re.compile(r"ignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+(instructions|rules)|disregard\s+(your|the)\s+(instructions|rules|system prompt)", re.I)),
    ("medium", "shell-injection-risk", re.compile(r"shell\s*=\s*True|os\.system\(|subprocess\.[a-z_]+\([^)]*shell\s*=\s*True|\beval\(|\bexec\(")),
    ("medium", "network-call", re.compile(r"\b(curl|wget|nc|ncat)\s+|requests\.(get|post)|urllib\.request|fetch\(|http\.client|socket\.socket|WebFetch")),
    ("medium", "destructive-command", re.compile(r"\brm\s+-[a-zA-Z]*[rf]|\bsudo\b|\bchmod\s+(-R\s+)?[0-7]*7[0-7]*\b|\bmkfs\b|\bdd\s+if=|git\s+push\s+(-f|--force)|git\s+reset\s+--hard")),
    ("medium", "reads-secrets-env", re.compile(r"(os\.environ|getenv|process\.env|\$\{?)[^\n]{0,40}(KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL)", re.I)),
    ("medium", "reads-dotenv", re.compile(r"\.env\b(?!ironment)")),
    ("low", "downloads-or-installs", re.compile(r"\b(pip3?|npm|npx|brew|apt(-get)?|gem|cargo)\s+(install|i|add)\b")),
]
INVISIBLE = re.compile("[​‌‍⁠﻿‪-‮⁦-⁩]")
BROAD_TOOLS = {"bash", "write", "edit", "webfetch", "websearch", "*"}


def home() -> Path:
    override = os.environ.get("SKILLGATE_HOME")
    if override:
        return Path(override).expanduser()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "skillgate"
    return Path.home() / ".local" / "state" / "skillgate"


def now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(folder: Path) -> str:
    """One hash for the whole skill: every path (and link target) and content, in sorted order."""
    digest = hashlib.sha256()
    for path in sorted(p for p in folder.rglob("*") if not p.is_dir()):
        rel = str(path.relative_to(folder))
        digest.update(rel.encode() + b"\0")
        digest.update((os.readlink(path).encode() if path.is_symlink() else sha(path).encode()) + b"\0")
    return digest.hexdigest()


def log(event: str, skill_id: str, **extra) -> None:
    root = home()
    root.mkdir(parents=True, exist_ok=True)
    with (root / "audit.log").open("a") as handle:
        handle.write(json.dumps({"time": now(), "event": event, "id": skill_id, **extra}) + "\n")


def meta_path(skill_id: str) -> Path:
    return home() / "meta" / f"{skill_id}.json"


def load_meta(skill_id: str) -> dict:
    path = meta_path(skill_id)
    if not path.exists():
        sys.exit(f"No such quarantined skill: {skill_id}")
    return json.loads(path.read_text())


def save_meta(skill_id: str, meta: dict) -> None:
    meta_path(skill_id).parent.mkdir(parents=True, exist_ok=True)
    meta_path(skill_id).write_text(json.dumps(meta, indent=2))


def quarantine_dir(skill_id: str) -> Path:
    return home() / "quarantine" / skill_id


def read_frontmatter(skill_md: Path) -> dict:
    """The simple `key: value` lines between the first two `---` lines. No YAML library needed."""
    if not skill_md.exists():
        return {}
    lines = skill_md.read_text(errors="replace").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    data = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            data[key.strip().lower()] = value.strip()
    return data


def scan_folder(folder: Path) -> list[dict]:
    """The deterministic checks. Same folder in, same findings out."""
    findings: list[dict] = []

    def add(severity, rule, file, line=0, excerpt=""):
        findings.append({"severity": severity, "rule": rule, "file": file, "line": line, "excerpt": excerpt[:100]})

    root = folder.resolve()
    skill_md = folder / "SKILL.md"
    if not skill_md.exists():
        add("medium", "no-skill-md", ".", 0, "no SKILL.md at the top of the folder")
    meta = read_frontmatter(skill_md)
    for field in ("name", "description"):
        if skill_md.exists() and not meta.get(field):
            add("low", "missing-frontmatter", "SKILL.md", 1, f"no {field} in the frontmatter")
    granted = {t.strip().lower() for t in re.split(r"[,\s]+", meta.get("allowed-tools", meta.get("tools", ""))) if t.strip()}
    broad = sorted(t for t in granted if t.split("(")[0] in BROAD_TOOLS)
    if broad:
        add("medium", "broad-tool-grant", "SKILL.md", 1, "grants: " + ", ".join(broad))
    if "hooks" in meta or (folder / "hooks").exists():
        add("high", "defines-hooks", "SKILL.md", 1, "hooks run commands automatically")

    for path in sorted(p for p in folder.rglob("*") if not p.is_dir() or p.is_symlink()):
        rel = str(path.relative_to(folder))
        if path.is_symlink():
            target = (path.parent / os.readlink(path)).resolve()
            if root not in target.parents and target != root:
                add("high", "symlink-escapes", rel, 0, f"link points outside the skill: {os.readlink(path)}")
            continue
        if path.name.startswith(".") and path.name not in (".gitignore",):
            add("low", "hidden-file", rel)
        size = path.stat().st_size
        if size > MAX_BYTES:
            add("medium", "large-file", rel, 0, f"{size} bytes")
        if path.stat().st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            add("low", "executable-bit", rel)
        raw = path.read_bytes()[:MAX_BYTES]
        if b"\x00" in raw[:4096] or path.suffix.lower() in {".zip", ".gz", ".tar", ".tgz", ".exe", ".dylib", ".so", ".bin", ".jar", ".whl"}:
            add("high", "binary-or-archive", rel, 0, "opaque content that cannot be read or reviewed")
            continue
        if path.suffix.lower() in SCRIPT_SUFFIXES:
            add("low", "contains-script", rel)
        text = raw.decode("utf-8", errors="replace")
        before = len(findings)
        for lineno, line in enumerate(text.splitlines(), 1):
            if INVISIBLE.search(line):
                add("high", "invisible-characters", rel, lineno, "zero-width or direction-control characters")
            for severity, rule, pattern in RULES:
                if pattern.search(line):
                    if rule == "network-call" and re.search(r"localhost|127\.0\.0\.1|\[::1\]", line):
                        continue  # talking to your own machine is not a leak
                    add(severity, rule, rel, lineno, line.strip())
    # A file that both reads a secret and talks to the network has the shape of an exfiltration, whatever it says it does.
    for rel in sorted({f["file"] for f in findings}):
        rules_here = {f["rule"] for f in findings if f["file"] == rel}
        if {"reads-secrets-env", "network-call"} <= rules_here or {"reads-credentials", "network-call"} <= rules_here:
            first = next(f for f in findings if f["file"] == rel and f["rule"] in ("reads-secrets-env", "reads-credentials"))
            add("high", "possible-exfiltration", rel, first["line"], "reads a secret and makes network calls in the same file")
    order = {s: i for i, s in enumerate(reversed(SEVERITY))}
    return sorted(findings, key=lambda f: (order[f["severity"]], f["file"], f["line"], f["rule"]))


def severity_counts(issues: list[dict]) -> int:
    return sum(1 for i in issues if str(i.get("severity", "")).lower() in ("high", "critical"))


def count_serious(node) -> int:
    """For a scanner whose report format we have not seen: count anything labelled high or critical."""
    if isinstance(node, dict):
        here = 1 if str(node.get("severity", "")).lower() in ("high", "critical") else 0
        return here + sum(count_serious(v) for v in node.values())
    if isinstance(node, list):
        return sum(count_serious(v) for v in node)
    return 0


def not_run(name: str, privacy: str, why: str) -> dict:
    return {"name": name, "privacy": privacy, "ran": False, "high_findings": 0, "summary": why}


def adapter_skillspector(binary: str | None, folder: Path, outdir: Path) -> dict:
    """NVIDIA SkillSpector, static pass only (`--no-llm`): local, no content leaves the machine.
    Report fields (checked against v2.12): risk_assessment{score, severity, recommendation}, issues[{severity, category, location}]."""
    if not binary:
        return not_run("skillspector", "local", "not installed")
    out = outdir / "skillspector.json"
    done = subprocess.run([binary, "scan", str(folder), "--no-llm", "--format", "json", "--output", str(out)], capture_output=True, text=True)
    if not out.exists():
        return not_run("skillspector", "local", "failed: " + (done.stderr or done.stdout).strip()[:120])
    report = json.loads(out.read_text())
    issues = report.get("issues") if isinstance(report, dict) else None
    if isinstance(issues, list):
        high = severity_counts(issues)
        risk = report.get("risk_assessment", {})
        if str(risk.get("recommendation", "")).upper() == "DO_NOT_INSTALL" and not high:
            high = 1
        summary = f"risk score {risk.get('score', '?')} ({risk.get('severity', '?')}), {len(issues)} issue(s)"
    else:
        high, summary = count_serious(report), "report format not recognized; counted high/critical labels"
    return {"name": "skillspector", "privacy": "local", "ran": True, "high_findings": high, "summary": summary, "report": str(out)}


def adapter_agent_scan(binary: str | None, folder: Path, outdir: Path, allowed: bool) -> dict:
    """Snyk agent-scan. REMOTE: it sends the skill's content to Snyk's service (secrets redacted) and needs SNYK_TOKEN.
    Only runs with --remote. Output parsing is generic: we have not seen its real report."""
    if not allowed:
        return not_run("agent-scan", "remote", "skipped: sends skill content to Snyk; pass --remote to allow")
    if not binary:
        return not_run("agent-scan", "remote", "not installed (snyk-agent-scan)")
    if not os.environ.get("SNYK_TOKEN"):
        return not_run("agent-scan", "remote", "SNYK_TOKEN is not set")
    target = folder / "SKILL.md" if (folder / "SKILL.md").exists() else folder
    import shlex
    done = subprocess.run([*shlex.split(binary), str(target), "--json"], capture_output=True, text=True)  # binary may be e.g. "uvx snyk-agent-scan@0.6.0"
    try:
        report = json.loads(done.stdout)
    except ValueError:
        return not_run("agent-scan", "remote", "failed or gave no JSON: " + (done.stderr or done.stdout).strip()[:120])
    out = outdir / "agent-scan.json"
    out.write_text(json.dumps(report))
    # Checked against v0.6.8: {"scan_path_responses": [{"client", "path", "server_risks": [], "skill_risks": [], "error": {...}}]}.
    # A response with an error means nothing was analyzed. That is "did not run", never "clean".
    responses = report.get("scan_path_responses") if isinstance(report, dict) else None
    if isinstance(responses, list):
        failures = [r["error"] for r in responses if isinstance(r, dict) and isinstance(r.get("error"), dict)]
        if failures or not responses:
            why = (failures[0].get("message") if failures else "no scan results") or "failed"
            return not_run("agent-scan", "remote", "failed, nothing analyzed: " + str(why)[:140])
        risks = [x for r in responses for key in ("skill_risks", "server_risks") for x in (r.get(key) or [])]
        # We have not seen a risk entry. Fail closed: any entry counts as high, and so does any labelled high or critical.
        high = max(len(risks), count_serious(risks))
        return {"name": "agent-scan", "privacy": "remote", "ran": True, "high_findings": high,
                "summary": f"{len(risks)} risk indicator(s)", "report": str(out)}
    return {"name": "agent-scan", "privacy": "remote", "ran": True, "high_findings": count_serious(report),
            "summary": "ran (report format not recognized)", "report": str(out)}


def vt_token_from_file() -> str:
    """The token file VirusTotal's own guide writes: one line, `Authorization: Bearer <token>`."""
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "vtai" / "auth.header"
    try:
        line = path.read_text().strip()
    except OSError:
        return ""
    return line.split("Bearer", 1)[1].strip() if "Bearer" in line else ""


def adapter_virustotal(folder: Path, allowed: bool) -> dict:
    """VirusTotal hash lookups. REMOTE, but only file hashes leave the machine, never content. Needs VT_AGENT_TOKEN.
    A file VirusTotal has never seen proves nothing, and neither does a clean result; both are reported as unknown or clean, not safe."""
    if not allowed:
        return not_run("virustotal", "remote", "skipped: pass --vt to look up file hashes (hashes only, no content)")
    token = os.environ.get("VT_AGENT_TOKEN") or vt_token_from_file()
    if not token:
        return not_run("virustotal", "remote", "no Agent Token: set VT_AGENT_TOKEN (section 9.3)")
    import urllib.error
    import urllib.request
    base = os.environ.get("VT_BASE_URL", "https://ai.virustotal.com/api/v3").rstrip("/")
    files = sorted(p for p in folder.rglob("*") if p.is_file() and not p.is_symlink())[:20]  # stay inside the rate limit
    malicious, unknown, clean, errors = [], 0, 0, 0
    for path in files:
        request = urllib.request.Request(f"{base}/files/{sha(path)}", headers={"x-apikey": token})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                data = json.load(response)["data"]
                # Checked against ai.virustotal.com's OpenAPI: data.last_analysis_stats and data.detections.
                # Classic VirusTotal nests the stats under data.attributes, so accept that too.
                stats = data.get("last_analysis_stats") or data.get("attributes", {}).get("last_analysis_stats", {})
                detections = data.get("detections") or []
        except urllib.error.HTTPError as err:
            unknown, errors = unknown + (err.code == 404), errors + (err.code != 404)
            continue
        except Exception:  # noqa: BLE001
            errors += 1
            continue
        if stats.get("malicious", 0) or stats.get("suspicious", 0) or detections:
            malicious.append(str(path.relative_to(folder)))
        else:
            clean += 1
    summary = f"{len(files)} hash(es): {len(malicious)} flagged, {clean} clean, {unknown} unknown to VirusTotal, {errors} error(s)"
    return {"name": "virustotal", "privacy": "remote", "ran": errors < len(files) or not files, "high_findings": len(malicious),
            "summary": summary + (" (flagged: " + ", ".join(malicious[:5]) + ")" if malicious else "")}


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def verify_review(folder: Path, review: dict) -> dict:
    """Does each quote the reviewer cites exist, in the file it names? An invented quote is a red flag."""
    problems, checked = [], 0
    for key in ("purpose", "matches_description", "verdict", "evidence"):
        if key not in review:
            problems.append(f"review is missing '{key}'")
    if review.get("verdict") not in ("allow", "review", "block"):
        problems.append("verdict must be allow, review or block")
    evidence = review.get("evidence") if isinstance(review.get("evidence"), list) else []
    for item in evidence:
        checked += 1
        file, quote = str(item.get("file", "")), str(item.get("quote", ""))
        target = (folder / file).resolve()
        if folder.resolve() not in target.parents or not target.is_file():
            problems.append(f"cites a file that is not in the skill: {file[:60]}")
        elif not quote or normalize(quote) not in normalize(target.read_text(errors="replace")):
            problems.append(f"quote not found in {file[:60]}")
    if review.get("verdict") in ("review", "block") and not evidence:
        problems.append("a review or block verdict must cite evidence")
    return {"ok": not problems, "problems": problems, "checked": checked}


def decide(meta: dict) -> tuple[str, list[str]]:
    reasons: list[str] = []
    scan = meta.get("scan")
    review = meta.get("review")
    if not scan:
        return "unscanned", ["run scan first"]
    highs = [f for f in scan["findings"] if f["severity"] == "high"]
    if highs:
        reasons.append(f"{len(highs)} high-severity finding(s): " + ", ".join(sorted({f['rule'] for f in highs})))
    scanners = scan.get("scanners", {})
    for name, result in scanners.items():
        if result.get("ran") and result.get("high_findings"):
            reasons.append(f"{name} reported {result['high_findings']} high or critical finding(s)")
    if review and review.get("verdict") == "block":
        reasons.append("the reviewer's verdict is block")
    if reasons:
        return "blocked", reasons
    if not review:
        return "needs-human", ["no reviewer verdict yet"]
    mediums = [f for f in scan["findings"] if f["severity"] == "medium"]
    if not review.get("verification", {}).get("ok"):
        reasons.append("the reviewer's evidence did not verify: " + "; ".join(review.get("verification", {}).get("problems", ["not verified"]))[:200])
    if review.get("verdict") == "review":
        reasons.append("the reviewer asks for a human look")
    if mediums:
        reasons.append(f"{len(mediums)} medium-severity finding(s): " + ", ".join(sorted({f['rule'] for f in mediums})))
    if not any(r.get("ran") and r.get("privacy") == "local" for r in scanners.values()):
        reasons.append("no outside scanner ran locally (install SkillSpector)")
    if reasons:
        return "needs-human", reasons
    return "release-candidate", ["no high findings, reviewer allows, evidence verified"]


def cmd_quarantine(args) -> None:
    src = Path(args.skill).expanduser()
    if not src.is_dir():
        sys.exit(f"Not a folder: {src}")
    digest = tree_hash(src)
    skill_id = f"{re.sub(r'[^A-Za-z0-9._-]+', '-', src.resolve().name)}-{digest[:12]}"
    dest = quarantine_dir(skill_id)
    if dest.exists():
        print(f"Already in quarantine: {skill_id}")
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dest, symlinks=True)
    for path in dest.rglob("*"):
        if not path.is_symlink() and not path.is_dir():
            path.chmod(0o444)  # read-only, and nothing in here can be executed by accident
    save_meta(skill_id, {"id": skill_id, "source": str(src.resolve()), "origin": args.origin or "not recorded",
                         "tree_hash": digest, "quarantined": now(), "state": "quarantined"})
    log("quarantine", skill_id, origin=args.origin or "not recorded")
    print(f"Quarantined as {skill_id}. Next: scan it.")


def cmd_scan(args) -> None:
    meta = load_meta(args.id)
    folder = quarantine_dir(args.id)
    if tree_hash(folder) != meta["tree_hash"]:
        sys.exit("The quarantined files changed since they were copied. Re-quarantine from the source.")
    findings = scan_folder(folder)
    scan = {"time": now(), "findings": findings}
    outdir = home() / "meta" / f"{args.id}.reports"
    outdir.mkdir(parents=True, exist_ok=True)
    scan["scanners"] = {
        "skillspector": adapter_skillspector(args.skillspector or shutil.which("skillspector"), folder, outdir),
        "agent-scan": adapter_agent_scan(args.agent_scan or shutil.which("snyk-agent-scan") or shutil.which("agent-scan"), folder, outdir, args.remote),
        "virustotal": adapter_virustotal(folder, args.vt),
    }
    meta["scan"] = scan
    meta.pop("review", None)
    state, reasons = decide(meta)
    meta["state"], meta["reasons"] = state, reasons
    save_meta(args.id, meta)
    log("scan", args.id, findings=len(findings), scanners={n: r["ran"] for n, r in scan["scanners"].items()})
    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in reversed(SEVERITY)}
    print(f"{args.id}: {counts['high']} high, {counts['medium']} medium, {counts['low']} low. State: {state}.")
    for name, result in scan["scanners"].items():
        print(f"  {name:12} {'ran' if result['ran'] else 'no ':3} ({result['privacy']}): {result['summary']}")
    for finding in findings[:25]:
        print(f"  {finding['severity']:6} {finding['rule']:22} {finding['file']}:{finding['line']}")


def cmd_verify(args) -> None:
    meta = load_meta(args.id)
    review = json.loads(Path(args.review).read_text())
    result = verify_review(quarantine_dir(args.id), review)
    meta["review"] = {"verdict": review.get("verdict"), "purpose": str(review.get("purpose", ""))[:300],
                      "matches_description": review.get("matches_description"), "verification": result, "time": now()}
    state, reasons = decide(meta)
    meta["state"], meta["reasons"] = state, reasons
    save_meta(args.id, meta)
    log("review", args.id, verdict=review.get("verdict"), verified=result["ok"])
    print(f"Reviewer verdict: {review.get('verdict')}. Evidence checked: {result['checked']}, "
          f"{'all verified' if result['ok'] else 'PROBLEMS: ' + '; '.join(result['problems'])}. State: {state}.")


def cmd_decide(args) -> None:
    meta = load_meta(args.id)
    state, reasons = decide(meta)
    meta["state"], meta["reasons"] = state, reasons
    save_meta(args.id, meta)
    print(f"{args.id}: {state}")
    for reason in reasons:
        print(f"  - {reason}")


def cmd_release(args) -> None:
    meta = load_meta(args.id)
    folder = quarantine_dir(args.id)
    state, reasons = decide(meta)
    if not args.yes:
        sys.exit("Releasing needs --yes, typed by a person who has read the findings.")
    if tree_hash(folder) != meta["tree_hash"]:
        sys.exit("The quarantined files changed since they were scanned. Nothing released.")
    if state == "blocked" and not args.accept_risk:
        sys.exit("Blocked: " + "; ".join(reasons) + ". A person can override with --accept-risk \"reason\"; it is logged.")
    if state not in ("release-candidate", "needs-human", "blocked"):
        sys.exit(f"Cannot release from state '{state}': " + "; ".join(reasons))
    target = Path(args.target).expanduser() / Path(meta["source"]).name
    if target.exists():
        sys.exit(f"{target} already exists. Remove or rename it first; nothing was overwritten.")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(folder, target, symlinks=True)
    for path in target.rglob("*"):
        if not path.is_symlink():
            path.chmod(0o755 if path.is_dir() else 0o644)
    index = home() / "released.json"
    released = json.loads(index.read_text()) if index.exists() else {}
    released[str(target.resolve())] = {"id": args.id, "tree_hash": meta["tree_hash"], "released": now(), "state_at_release": state,
                                       "accepted_risk": args.accept_risk or ""}
    index.write_text(json.dumps(released, indent=2))
    meta["state"] = "released"
    save_meta(args.id, meta)
    log("release", args.id, target=str(target), state_at_release=state, accepted_risk=args.accept_risk or "")
    print(f"Released to {target} (state at release: {state}). `audit` will tell you if it changes.")


def cmd_audit(args) -> None:
    index = home() / "released.json"
    released = json.loads(index.read_text()) if index.exists() else {}
    target = Path(args.target).expanduser().resolve()
    bad = 0
    for path, info in released.items():
        if Path(path).parent != target:
            continue
        if not Path(path).is_dir():
            print(f"MISSING  {path}")
            bad += 1
        elif tree_hash(Path(path)) != info["tree_hash"]:
            print(f"CHANGED  {path}: differs from what was released ({info['released']}). Re-quarantine and re-scan it.")
            bad += 1
        else:
            print(f"ok       {path}")
    unknown = [p.name for p in target.iterdir() if p.is_dir() and str(p) not in released] if target.is_dir() else []
    for name in unknown:
        print(f"UNGATED  {target / name}: never went through the gate")
        bad += 1
    sys.exit(1 if bad else 0)


def cmd_status(args) -> None:
    ids = [args.id] if args.id else sorted(p.stem for p in (home() / "meta").glob("*.json") if not p.name.endswith(".skillspector.json"))
    for skill_id in ids:
        meta = load_meta(skill_id)
        print(f"{skill_id}  {meta.get('state')}  origin: {meta.get('origin')}")
        for reason in meta.get("reasons", []):
            print(f"    - {reason}")


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("quarantine"); p.add_argument("skill"); p.add_argument("--origin"); p.set_defaults(run=cmd_quarantine)
    p = sub.add_parser("scan"); p.add_argument("id"); p.add_argument("--skillspector"); p.add_argument("--agent-scan")
    p.add_argument("--remote", action="store_true", help="allow scanners that send skill content to a remote service (Snyk agent-scan)")
    p.add_argument("--vt", action="store_true", help="look up file hashes on VirusTotal (hashes only)"); p.set_defaults(run=cmd_scan)
    p = sub.add_parser("verify-review"); p.add_argument("id"); p.add_argument("review"); p.set_defaults(run=cmd_verify)
    p = sub.add_parser("decide"); p.add_argument("id"); p.set_defaults(run=cmd_decide)
    p = sub.add_parser("release"); p.add_argument("id"); p.add_argument("--target", required=True)
    p.add_argument("--yes", action="store_true"); p.add_argument("--accept-risk"); p.set_defaults(run=cmd_release)
    p = sub.add_parser("audit"); p.add_argument("--target", required=True); p.set_defaults(run=cmd_audit)
    p = sub.add_parser("status"); p.add_argument("id", nargs="?"); p.set_defaults(run=cmd_status)
    args = ap.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
