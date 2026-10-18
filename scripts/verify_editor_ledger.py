"""Check an editor agent's report against the files. A claim that the skill was run is only worth what can be verified.

    python3 scripts/verify_editor_ledger.py <report.txt>

The editor must end its report with a ledger (see .claude/agents/editor.md). This script confirms the ledger exists, says the
skill loaded, and names the real last heading of the skill's catalog. That catches an agent that skipped the end by accident.
It does not stop one that looks the heading up on purpose: a single grep finds it. Exit 0 when the ledger checks out, 1 when
it does not.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / ".claude" / "skills" / "avoid-ai-writing" / "references" / "patterns.md"


def last_heading(text: str) -> str:
    headings = [m.group(1).strip() for m in re.finditer(r"^#+\s+(.+)$", text, re.M)]
    return headings[-1] if headings else ""


def verify(report: str, catalog_text: str) -> list[str]:
    problems = []
    if "Ledger" not in report:
        return ["no Ledger block"]
    ledger = report[report.index("Ledger"):]
    if not re.search(r"Skill loaded:\s*yes", ledger, re.I):
        problems.append("the ledger does not say the skill loaded")
    match = re.search(r"Catalog read through:\s*(.+)", ledger)
    expected = last_heading(catalog_text)
    if not match:
        problems.append("the ledger does not say how far the catalog was read")
    elif expected.lower() not in match.group(1).strip().lower():
        problems.append("the catalog's last heading is not what the ledger says")
    for field in ("Linter findings", "Editing passes"):
        if field not in ledger:
            problems.append(f"the ledger is missing '{field}'")
    return problems


def main() -> None:
    if len(sys.argv) == 2 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    problems = verify(Path(sys.argv[1]).read_text(), CATALOG.read_text())
    for problem in problems:
        print(f"  - {problem}")
    print("Ledger verified." if not problems else f"Ledger FAILED ({len(problems)} problem(s)).")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
