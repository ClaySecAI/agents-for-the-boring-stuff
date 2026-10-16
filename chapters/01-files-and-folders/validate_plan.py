"""Ask Claude to sanity-check a plan, with NO access to your files.

    python validate_plan.py <claude-view.txt> [--model haiku]

Claude gets only claude-view.txt (ids, extensions, sizes, labels, destination
folders). No filenames, no contents. The privacy boundary is enforced by the
tool list, not by asking nicely:

  * `--tools ""`   : no built-in tools (no Read, Bash, Grep...), so it cannot open any
                     file even if the metadata tempted it to.
  * `--strict-mcp-config` + an empty MCP list : ALSO drop connector tools. We learned
                     this the hard way: `--tools ""` alone still left the account's
                     claude.ai connectors (Docs, Strava...) callable by the model.
  * `--no-chrome`, `--no-session-persistence` : no browser tools, nothing saved to disk.
  * `cwd` = empty temp directory : no project settings, skills or CLAUDE.md load.
  * `--system-prompt-file`       : replaces the default coding-agent prompt.

Exit code 0 means "approve", 1 means "flag" (flags are printed). Use it as a gate
before apply_plan.py.
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

PROMPT = Path(__file__).with_name("validator-prompt.md")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("view", type=Path)
    ap.add_argument("--model", default="haiku")
    args = ap.parse_args()

    view = args.view.read_text()
    with tempfile.TemporaryDirectory() as empty_dir:
        result = subprocess.run(
            ["claude", "-p", "--tools", "", "--model", args.model,
             "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}',
             "--no-chrome", "--no-session-persistence",
             "--system-prompt-file", str(PROMPT.resolve()),
             "--disable-slash-commands"],
            input=view, capture_output=True, text=True, cwd=empty_dir, timeout=180)
    if result.returncode != 0:
        sys.exit(f"claude failed: {result.stderr.strip() or result.stdout.strip()}")

    match = re.search(r"\{.*\}", result.stdout, re.DOTALL)
    try:
        verdict = json.loads(match.group(0))
    except (AttributeError, json.JSONDecodeError):
        sys.exit(f"Could not read the validator's answer:\n{result.stdout}")

    flags = verdict.get("flags", [])
    if verdict.get("verdict") == "approve" and not flags:
        print("Claude: approve. Nothing looks wrong from the metadata.")
        return
    print(f"Claude: flag. {len(flags)} file(s) deserve a human look before anything moves:")
    for flag in flags:
        print(f"  - {flag['id']}: {flag['reason']}")
    sys.exit(1)


if __name__ == "__main__":
    main()
