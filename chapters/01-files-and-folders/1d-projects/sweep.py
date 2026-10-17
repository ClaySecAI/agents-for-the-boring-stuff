"""Sort the new loose files in a folder into the project folders you already have. Built to run weekly.

    python3 sweep.py init   [--config FILE] <folder>      write a starting config and project list
    python3 sweep.py run    [--config FILE] [--dry-run] [--if-due DAYS]   one sweep: propose, check, apply, verify
    python3 sweep.py undo   [--config FILE] [RUN]         put back the files of one sweep (default: the latest)
    python3 sweep.py status [--config FILE]               the last sweeps, as counts
    python3 sweep.py folders [--config FILE]              folders that are not projects and have no rule
    python3 sweep.py agent  [--config FILE]               print a launchd job that sweeps once a week

The one-time sort in the rest of this chapter looks at everything and asks you to approve a plan. A
sweep does the same work on a schedule, so the approval is replaced by gates written in code. A sweep
only ever moves a loose file into one of your project folders. It never touches a subfolder, never
deletes, never overwrites, and stops with nothing moved when a gate fails.

A file is eligible when it sits directly in the folder, is not hidden, is on disk (not an iCloud
placeholder), is not empty, is not a partial download, and was last changed more than min_age_minutes
ago, so a file still being written is left alone.

The gates, all in config.json:

  max_moves             a sweep that would move more files than this moves none and tells you
  min_battery_percent   on battery below this percent the sweep skips itself, without counting as a sweep
                        (default 50; plugged in always runs; 0 turns the check off)
  manage_model          true: start LM Studio's server and load the model for the sweep, then unload and
                        stop what it started. false: use a server that is already running
  hold_sensitivities    files the model labelled with one of these stay where they are (default:
                        credentials, unknown); they are counted, never moved
  unsorted              files the model cannot place stay where they are
  every move is written to an undo record in the run's folder BEFORE the first move
  afterwards each moved file is hashed again; one mismatch undoes the whole sweep

Folders that are not projects need a rule, because a sweep never opens a subfolder. In config.json,
folder_rules maps a folder name to what to do with it:

  "EventPhotos Download (123456789)": {"unit": "Cycling event photos"}

moves that folder, whole and unopened, into the named project's folder. A folder with no rule is left
alone and counted as untracked in the report; `sweep.py folders` lists them. A folder whose files
belong in several projects (an "attachments" folder) is sorted file by file in a separate, approved
run, as in the rest of this chapter, and not by a sweep.

Everything a sweep writes goes under state_dir (default ~/Library/Application Support/downloads-sweep):
one folder per run with the plan, the assignments, the undo record and a report. The plan and undo
record hold file names; the report holds only counts, and so does the notification macOS shows.

Nothing in a sweep leaves your machine. The model is a local one; Claude is not involved.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import plistlib
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(HERE))
from plan_common import IGNORED_NAMES  # noqa: E402

LABEL = "local.boringstuff.downloads-sweep"
PARTIAL = {".download", ".crdownload", ".part", ".partial", ".tmp", ".opdownload"}
DEFAULTS = {
    "folder": str(Path.home() / "Downloads"),
    "projects_file": "projects.json",
    "model": "google/gemma-4-e4b",
    "base_url": "http://localhost:1234/v1",
    "min_age_minutes": 60,
    "max_moves": 100,
    "hold_sensitivities": ["credentials", "unknown"],
    "min_battery_percent": 50,
    "folder_rules": {},
    "manage_model": True,
    "state_dir": str(Path.home() / "Library" / "Application Support" / "downloads-sweep"),
}


def default_config_path() -> Path:
    return Path(DEFAULTS["state_dir"]) / "config.json"


def load_config(path: Path | None) -> dict:
    path = path or default_config_path()
    if not path.is_file():
        sys.exit(f"No config at {path}. Run: python3 sweep.py init <folder>")
    config = {**DEFAULTS, **json.loads(path.read_text())}
    config["_dir"] = path.resolve().parent
    return config


def is_dataless(path: Path) -> bool:
    """True for an iCloud placeholder: the file's data is not on this Mac."""
    flags = getattr(path.lstat(), "st_flags", 0)
    return bool(flags & 0x40000000)  # SF_DATALESS


def eligible(folder: Path, min_age_minutes: float, now: float | None = None) -> tuple[list[str], dict]:
    """Loose files a sweep may touch, and counts of the ones it skipped and why."""
    now = time.time() if now is None else now
    keep, skipped = [], {"hidden": 0, "recent": 0, "partial": 0, "empty": 0, "cloud_only": 0, "not_a_file": 0}
    for item in sorted(folder.iterdir()):
        if item.name in IGNORED_NAMES:
            continue
        if item.name.startswith("."):
            skipped["hidden"] += 1
        elif item.is_symlink() or not item.is_file():
            skipped["not_a_file"] += 1
        elif item.suffix.lower() in PARTIAL:
            skipped["partial"] += 1
        elif is_dataless(item):
            skipped["cloud_only"] += 1
        elif item.stat().st_size == 0:
            skipped["empty"] += 1
        elif now - item.stat().st_mtime < min_age_minutes * 60:
            skipped["recent"] += 1
        else:
            keep.append(item.name)
    return keep, skipped


def unit_moves(folder: Path, rules: dict, names: list[str], min_age_minutes: float, now: float | None = None) -> dict[str, str]:
    """Folders with a {"unit": project} rule that exist, are not hidden, and are settled. {folder name: project}."""
    now = time.time() if now is None else now
    result = {}
    for name, rule in rules.items():
        path = folder / name
        project = rule.get("unit")
        if project in names and path.is_dir() and not path.is_symlink() and not name.startswith("."):
            if now - path.stat().st_mtime >= min_age_minutes * 60:
                result[name] = project
    return result


def untracked_folders(folder: Path, names: list[str], rules: dict) -> list[str]:
    known = {folder_name(n) for n in names} | set(rules)
    return sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.is_symlink()
                  and not p.name.startswith((".", "_")) and p.name not in known)


def decide(assigned: dict, names: list[str], hold: list[str]) -> tuple[dict, dict]:
    """(moves {file: project}, held counts). Only a file placed in a listed project, and not held, moves."""
    moves, held = {}, {"unsorted": 0, "sensitive": 0}
    for rel, label in assigned.items():
        if label.get("primary") not in names:
            held["unsorted"] += 1
        elif label.get("sensitivity", "unknown") in hold:
            held["sensitive"] += 1
        else:
            moves[rel] = label["primary"]
    return moves, held


def folder_name(project: str) -> str:
    return "".join("-" if c in "\\/|:;" else c for c in project).strip(". ") or "Project"


def destinations(folder: Path, moves: dict[str, str]) -> dict[str, str]:
    """A free destination for every move. An existing file is never overwritten: the newcomer gets (2), (3)..."""
    taken: set[str] = set()
    result = {}
    for rel, project in sorted(moves.items()):
        base = dest = f"{folder_name(project)}/{rel}"
        n = 2
        while dest in taken or (folder / dest).exists():
            stem, dot, ext = base.rpartition(".")
            dest = f"{stem} ({n}){dot}{ext}" if dot else f"{base} ({n})"
            n += 1
        taken.add(dest)
        result[rel] = dest
    return result


def write_plan(path: Path, folder: Path, dests: dict[str, str], assigned: dict) -> None:
    lines = ["# Weekly sweep of " + folder.name, "", "Mode: top-level", "", "| From | To | Why | Also |", "|---|---|---|---|"]
    for item in sorted(p.name for p in folder.iterdir() if p.name not in IGNORED_NAMES):
        if item in dests:
            label = assigned.get(item)
            why = (f"project={label['primary']} sensitivity={label.get('sensitivity', 'unknown')}" if label
                   else "folder rule, moved whole")
            lines.append(f"| {item} | {dests[item]} | {why} | |")
        else:
            lines.append(f"| {item} | {item} | left in place | |")
    path.write_text("\n".join(lines) + "\n")


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def power_ok(pmset_output: str, minimum: float) -> tuple[bool, str]:
    """(ok, why). Plugged in is always fine; on battery, only at or above `minimum` percent. Unknown is fine."""
    if "AC Power" in pmset_output:
        return True, "on AC power"
    import re
    found = re.search(r"(\d+)%", pmset_output)
    if "Battery Power" in pmset_output and found:
        percent = int(found.group(1))
        return percent >= minimum, f"on battery at {percent}%"
    return True, "no battery information"


def notify(text: str) -> None:
    """A macOS notification with counts only. Silent elsewhere."""
    if sys.platform == "darwin" and not os.environ.get("SWEEP_NO_NOTIFY"):
        script = f'display notification "{text}" with title "Downloads sweep"'
        subprocess.run(["osascript", "-e", script], capture_output=True)


def server_up(base_url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url}/models", timeout=3):
            return True
    except Exception:  # noqa: BLE001
        return False


def find_lms() -> str | None:
    return shutil.which("lms") or (str(p) if (p := Path.home() / ".lmstudio" / "bin" / "lms").exists() else None)


def run_script(script: str, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", script, *map(str, args)], capture_output=True, text=True,
                          env={**os.environ, **(env or {})})


def cmd_init(args) -> None:
    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        sys.exit(f"Not a folder: {folder}")
    state = Path(DEFAULTS["state_dir"])
    state.mkdir(parents=True, exist_ok=True)
    config_path = args.config or default_config_path()
    if config_path.exists():
        sys.exit(f"{config_path} already exists; edit it instead.")
    existing = sorted(p.name for p in folder.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))
    projects = [{"name": name, "description": "EDIT ME: one sentence on what belongs in this project."} for name in existing]
    (config_path.parent / "projects.json").write_text(json.dumps(projects, indent=2))
    config_path.write_text(json.dumps({**DEFAULTS, "folder": str(folder)}, indent=2))
    print(f"Wrote {config_path} and projects.json with {len(existing)} folders from {folder.name}.")
    print("Edit projects.json: keep the folders you want sweeps to file into, and give each a real description.")


def cmd_run(args) -> int:
    config = load_config(args.config)
    folder = Path(config["folder"]).expanduser()
    state = Path(config["state_dir"]).expanduser()
    if args.if_due is not None:
        age = days_since_last_sweep(runs(config))
        if age is not None and age < args.if_due:
            print(f"Not due: the last sweep was {age:.1f} days ago (every {args.if_due:g} days).")
            return 0
    if sys.platform == "darwin" and config.get("min_battery_percent", 0) > 0:
        pm = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
        ok, why = power_ok(pm, config["min_battery_percent"])
        if not ok:
            print(f"Skipped: {why}, below {config['min_battery_percent']}%. Not counted; it will try again.")
            return 0
    projects_file = Path(config["projects_file"])
    projects_file = projects_file if projects_file.is_absolute() else config["_dir"] / projects_file
    run_id = datetime.datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")[:-3]
    run_dir = state / "runs" / run_id
    run_dir.mkdir(parents=True)
    lock = state / "sweep.lock"
    try:
        lock.touch(exist_ok=False)
    except FileExistsError:
        if time.time() - lock.stat().st_mtime < 6 * 3600:
            print("Another sweep is running (or crashed within six hours); stopping.")
            return 1
        lock.touch()
    report: dict = {"run": run_id, "folder_items": 0}
    started_server = loaded = False
    lms = find_lms() if config.get("manage_model", True) else None
    try:
        try:
            list(folder.iterdir())
        except PermissionError:
            report["stopped"] = "macOS blocked access to the folder"
            return finish(report, run_dir, "stopped: no access to the folder")
        names = [p["name"] for p in json.loads(projects_file.read_text())]
        files, skipped = eligible(folder, config["min_age_minutes"])
        rules = config.get("folder_rules", {})
        units = unit_moves(folder, rules, names, config["min_age_minutes"])
        report.update(eligible=len(files), skipped=skipped, folders_by_rule=len(units),
                      untracked_folders=len(untracked_folders(folder, names, rules)))
        if not files and not units:
            return finish(report, run_dir, "nothing new to sort")

        if files and not server_up(config["base_url"]):
            if not lms:
                report["stopped"] = "no model server and no lms command"
                return finish(report, run_dir, "stopped: no model server")
            subprocess.run([lms, "server", "start"], capture_output=True)
            started_server = True
            for _ in range(20):
                if server_up(config["base_url"]):
                    break
                time.sleep(1)
        if files and lms:
            subprocess.run([lms, "unload", "--all"], capture_output=True)
            loaded = subprocess.run([lms, "load", config["model"], "-y", "--identifier", "sweep",
                                     "--context-length", "6144"], capture_output=True).returncode == 0
        assigned = {}
        if files:
            only = run_dir / "only.json"
            only.write_text(json.dumps(files))
            run_script(str(HERE / "assign_projects.py"), folder, projects_file, "--top-level", "--only", only,
                       "--model", "sweep", "--base-url", config["base_url"], "--out", run_dir / "assignments.json")
            if not (run_dir / "assignments.json").exists():
                report["stopped"] = "the model produced no answers"
                return finish(report, run_dir, "stopped: the model produced no answers")
            assigned = json.loads((run_dir / "assignments.json").read_text())
        moves, held = decide(assigned, names, config["hold_sensitivities"])
        moves.update(units)
        report.update(assigned=len(assigned), held=held, would_move=len(moves))
        if len(moves) > config["max_moves"]:
            report["stopped"] = f"{len(moves)} moves is over the limit of {config['max_moves']}"
            return finish(report, run_dir, f"stopped: {len(moves)} moves is over the limit, nothing moved")
        if not moves:
            return finish(report, run_dir, "nothing to move")
        dests = destinations(folder, moves)
        plan = run_dir / "organize-plan.md"
        write_plan(plan, folder, dests, assigned)
        env = {"PLAN_STATE_DIR": str(run_dir)}
        check = run_script(str(CH1 / "apply_plan.py"), "--check", plan, folder, env=env)
        if check.returncode != 0:
            report["stopped"] = "the plan failed its own checks"
            return finish(report, run_dir, "stopped: the plan failed its checks")
        if args.dry_run:
            report["dry_run"] = True
            return finish(report, run_dir, f"dry run: {len(moves)} items would move")
        before = {rel: sha(folder / rel) for rel in dests if rel not in units}
        applied = run_script(str(CH1 / "apply_plan.py"), plan, folder, env=env)
        bad = [rel for rel, dest in dests.items()
               if (folder / rel).exists() or not (folder / dest).exists()
               or (rel not in units and sha(folder / dest) != before[rel])]
        if applied.returncode != 0 or bad:
            run_script(str(CH1 / "undo_plan.py"), folder, env=env)
            report["stopped"] = "verification failed; the sweep was undone"
            return finish(report, run_dir, "verification failed; sweep undone", failed=True)
        report["moved"] = len(dests)
        return finish(report, run_dir, f"sorted {len(dests)} items, held {sum(held.values())}")
    finally:
        if lms and (started_server or loaded):
            subprocess.run([lms, "unload", "--all"], capture_output=True)
        if started_server and lms:
            subprocess.run([lms, "server", "stop"], capture_output=True)
        lock.unlink(missing_ok=True)


def finish(report: dict, run_dir: Path, summary: str, failed: bool = False) -> int:
    report["summary"] = summary
    (run_dir / "report.json").write_text(json.dumps(report, indent=2))
    print(summary)
    notify(summary)
    return 2 if failed else (1 if report.get("stopped") else 0)


def days_since_last_sweep(run_dirs: list[Path], now: datetime.datetime | None = None) -> float | None:
    """Days since the last sweep that really ran (not a dry run, not a stopped one). None if there is none."""
    now = now or datetime.datetime.now()
    latest = None
    for run_dir in run_dirs:
        report = run_dir / "report.json"
        if not report.exists():
            continue
        data = json.loads(report.read_text())
        if data.get("dry_run") or data.get("stopped"):
            continue
        try:
            stamp = datetime.datetime.strptime(run_dir.name[:17], "%Y-%m-%d-%H%M%S")
        except ValueError:
            continue
        latest = max(latest, stamp) if latest else stamp
    return None if latest is None else (now - latest).total_seconds() / 86400


def runs(config: dict) -> list[Path]:
    root = Path(config["state_dir"]).expanduser() / "runs"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def cmd_undo(args) -> int:
    config = load_config(args.config)
    chosen = [r for r in runs(config) if (args.run is None or r.name == args.run) and
              list(r.glob(".*applied-plan.md"))]
    if not chosen:
        sys.exit("No sweep to undo.")
    run_dir = chosen[-1]
    done = run_script(str(CH1 / "undo_plan.py"), Path(config["folder"]).expanduser(), env={"PLAN_STATE_DIR": str(run_dir)})
    print(done.stdout.strip() or done.stderr.strip())
    return done.returncode


def cmd_folders(args) -> None:
    config = load_config(args.config)
    projects_file = Path(config["projects_file"])
    projects_file = projects_file if projects_file.is_absolute() else config["_dir"] / projects_file
    names = [p["name"] for p in json.loads(projects_file.read_text())]
    found = untracked_folders(Path(config["folder"]).expanduser(), names, config.get("folder_rules", {}))
    print(f"{len(found)} folder(s) are not projects and have no rule:")
    for name in found:
        print(f"  {name}")
    print('Add a rule to config.json, e.g. "folder_rules": {"<folder>": {"unit": "<project>"}}, or leave them.')


def cmd_status(args) -> None:
    for run_dir in runs(load_config(args.config))[-10:]:
        report = run_dir / "report.json"
        text = json.loads(report.read_text()).get("summary", "?") if report.exists() else "no report"
        print(f"{run_dir.name}  {text}")


def cmd_agent(args) -> None:
    config = load_config(args.config)
    state = Path(config["state_dir"]).expanduser()
    plist = {
        "Label": LABEL,
        "ProgramArguments": [sys.executable, str(HERE / "sweep.py"), "run", "--if-due", "7",
                             "--config", str(config["_dir"] / "config.json")],
        # Checked every day at 03:00 (run on wake if the Mac was asleep) and at every login (a Mac that was
        # powered off at 03:00 never gets the missed run). --if-due keeps it to one real sweep a week.
        "StartCalendarInterval": {"Hour": 3, "Minute": 0},
        "RunAtLoad": True,
        "StandardOutPath": str(state / "sweep.log"),
        "StandardErrorPath": str(state / "sweep.log"),
        "EnvironmentVariables": {"PATH": f"{Path.home()}/.lmstudio/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin"},
    }
    sys.stdout.write(plistlib.dumps(plist).decode())


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    for name in ("init", "run", "undo", "status", "folders", "agent"):
        p = sub.add_parser(name)
        p.add_argument("--config", type=Path)
        if name == "init":
            p.add_argument("folder")
        if name == "run":
            p.add_argument("--dry-run", action="store_true")
            p.add_argument("--if-due", type=float, metavar="DAYS",
                           help="do nothing unless this many days have passed since the last real sweep")
        if name == "undo":
            p.add_argument("run", nargs="?")
    args = ap.parse_args()
    code = {"init": cmd_init, "run": cmd_run, "undo": cmd_undo, "status": cmd_status, "folders": cmd_folders, "agent": cmd_agent}[args.command](args)
    sys.exit(code or 0)


if __name__ == "__main__":
    main()
