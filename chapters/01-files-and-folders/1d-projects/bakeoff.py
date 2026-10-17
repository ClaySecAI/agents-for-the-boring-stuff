"""Compare local models on the same project-assignment task, with the same prompts and scoring.

    python3 bakeoff.py --models google/gemma-4-12b qwen/qwen3.5-9b --fixtures practice-projects practice-blind

Models are LM Studio model keys (see `lms ls`), or `ollama:<name>` for a model served by Ollama.
For each model and fixture it loads the model, runs assign_projects.py, scores the answers against the
fixture's answer key, times the run, and unloads the model. Models run one after another, because they
compete for the same memory.

The numbers worth comparing:

  right            files placed in their true project (the answer key says where)
  wrong project    files filed under a project that is NOT theirs: the costly kind of mistake
  left unsorted    files the model declined to place when they did belong somewhere
  failed           answers the server could not return in usable form
  seconds per file how long the model needed

--embed MODEL also scores a small embedding model, using embed_assign.py, for comparison.
Results are printed as a table and saved to --out as JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import score  # noqa: E402

OLLAMA_URL = "http://localhost:11434/v1"
LMS_URL = "http://localhost:1234/v1"


def lms(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["lms", *args], capture_output=True, text=True)


def tally(truth: dict, assigned: dict) -> dict:
    wrong = [f for f in truth if assigned.get(f, {}).get("primary", "Unsorted") != truth[f]["primary"]]
    forced = sum(1 for f in wrong if assigned.get(f, {}).get("primary", "Unsorted") != "Unsorted")
    return {"files": len(truth), "right": len(truth) - len(wrong), "wrong_project": forced,
            "left_unsorted": len(wrong) - forced}


def run_fixture(fixture: Path, model_name: str, base_url: str, tag: str, extra: list[str]) -> dict:
    out = fixture / f"assignments-bakeoff-{tag}.json"
    started = time.time()
    done = subprocess.run(
        [sys.executable, "-B", str(HERE / "assign_projects.py"), str(fixture / "downloads"),
         str(fixture / "projects.json"), "--model", model_name, "--base-url", base_url, "--out", str(out), *extra],
        capture_output=True, text=True)
    seconds = time.time() - started
    if not out.exists():
        return {"error": (done.stderr or done.stdout).strip().splitlines()[-1][:120] if (done.stderr or done.stdout) else "no output"}
    truth = json.loads((fixture / "truth.json").read_text())
    result = tally(truth, json.loads(out.read_text()))
    failed = re.search(r"(\d+) failed", done.stdout)
    result.update(failed=int(failed.group(1)) if failed else 0, seconds=round(seconds, 1),
                  sec_per_file=round(seconds / len(truth), 2))
    return result


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("--models", nargs="*", default=[])
    ap.add_argument("--fixtures", nargs="+", required=True)
    ap.add_argument("--embed", help="an embedding model key to include for comparison")
    ap.add_argument("--embed-margin", type=float, default=0.03)
    ap.add_argument("--context", default="6144")
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--out", type=Path, default=Path("bakeoff-results.json"))
    args = ap.parse_args()

    results: dict[str, dict] = {}
    if args.out.exists():
        results = json.loads(args.out.read_text())  # resume: keep what already ran

    for model in args.models:
        ollama = model.startswith("ollama:")
        name = model.split(":", 1)[1] if ollama else "bakeoff"
        base_url = OLLAMA_URL if ollama else LMS_URL
        entry = results.setdefault(model, {})
        if not ollama:
            lms("unload", "--all")
            loaded = lms("load", model, "-y", "--identifier", "bakeoff", "--context-length", args.context)
            if loaded.returncode != 0:
                reason = (loaded.stderr or loaded.stdout).strip().splitlines()
                entry["load_error"] = (reason[-1] if reason else "failed to load")[:140]
                print(f"{model}: did not load ({entry['load_error']})")
                args.out.write_text(json.dumps(results, indent=2))
                continue
        for fx in args.fixtures:
            if fx in entry and "error" not in entry[fx]:
                continue
            print(f"{model} on {fx} ...", flush=True)
            entry[fx] = run_fixture(Path(fx), name, base_url, model.replace("/", "_").replace(":", "_"),
                                    ["--max-tokens", str(args.max_tokens)])
            print(f"  {entry[fx]}", flush=True)
            args.out.write_text(json.dumps(results, indent=2))
        if not ollama:
            lms("unload", "--all")

    if args.embed:
        lms("unload", "--all")
        lms("load", args.embed, "-y", "--identifier", "embedder")
        entry = results.setdefault(f"embedding: {args.embed} (margin {args.embed_margin})", {})
        for fx in args.fixtures:
            fixture = Path(fx)
            out = fixture / "assignments-bakeoff-embed.json"
            started = time.time()
            subprocess.run([sys.executable, "-B", str(HERE / "embed_assign.py"), str(fixture / "downloads"),
                            str(fixture / "projects.json"), "--margin", str(args.embed_margin), "--out", str(out)],
                           capture_output=True, text=True)
            seconds = time.time() - started
            truth = json.loads((fixture / "truth.json").read_text())
            entry[fx] = {**tally(truth, json.loads(out.read_text())), "failed": 0, "seconds": round(seconds, 1),
                         "sec_per_file": round(seconds / len(truth), 2)}
        lms("unload", "--all")
        args.out.write_text(json.dumps(results, indent=2))

    print("\n" + render(results, args.fixtures))


def render(results: dict, fixtures: list[str]) -> str:
    lines = []
    for fx in fixtures:
        lines += [f"\n{fx}", "| model | right | wrong project | left unsorted | failed | seconds per file |",
                  "|---|---|---|---|---|---|"]
        for model, entry in results.items():
            r = entry.get(fx)
            if entry.get("load_error"):
                lines.append(f"| {model} | did not load: {entry['load_error']} | | | | |")
            elif r and "error" not in r:
                lines.append(f"| {model} | {r['right']}/{r['files']} | {r['wrong_project']} | {r['left_unsorted']} | "
                             f"{r['failed']} | {r['sec_per_file']} |")
            elif r:
                lines.append(f"| {model} | error: {r['error']} | | | | |")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
