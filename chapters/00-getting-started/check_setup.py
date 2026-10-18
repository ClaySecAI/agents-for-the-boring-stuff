"""Check what this computer has for the book's chapters. Changes nothing.

    python3 check_setup.py

Prints one line per item: ok, MISSING (needed), optional, or info. Nothing is installed and no file of yours is read.
"""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
import urllib.request


def version_of(command: list[str]) -> str:
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=15)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    text = (done.stdout or done.stderr).strip()
    return text.splitlines()[0] if text else "installed"


def server_models(base: str) -> list[str] | None:
    """Model names a local server offers, or None when nothing answers."""
    try:
        with urllib.request.urlopen(f"{base}/models", timeout=3) as response:
            return [m.get("id", "?") for m in json.load(response).get("data", [])]
    except Exception:  # noqa: BLE001 - any failure just means no server is there
        return None


def line(status: str, name: str, detail: str = "") -> None:
    print(f"{status:9} {name:28} {detail}")


def main() -> None:
    ok = sys.version_info >= (3, 9)
    line("ok" if ok else "MISSING", "Python 3.9 or later", platform.python_version())

    # On a Mac without developer tools, /usr/bin/git is a stub that prints a note instead of a version.
    git_version = version_of(["git", "--version"]) if shutil.which("git") else ""
    has_git = git_version.startswith("git version")
    line("ok" if has_git else "optional", "git", git_version if has_git else "clones the book; see 0B.4, or download the ZIP")

    claude = shutil.which("claude")
    line("ok" if claude else "MISSING", "claude (Claude Code)",
         version_of(["claude", "--version"]) if claude else "needed for the validation step")

    for name, why in (("lms", "LM Studio command line"), ("ollama", "Ollama")):
        found = shutil.which(name)
        line("ok" if found else "optional", name,
             ("installed" if name == "ollama" else version_of([name, "--version"])) if found else why)

    for name, base in (("LM Studio server", "http://localhost:1234/v1"), ("Ollama server", "http://localhost:11434/v1")):
        models = server_models(base)
        if models is None:
            line("optional", name, "not running")
        elif not models:
            line("optional", name, "running, no models loaded")
        else:
            line("ok", name, f"{len(models)} model(s): " + ", ".join(models[:4]) + (" ..." if len(models) > 4 else ""))

    if platform.system() == "Darwin":
        swiftc = shutil.which("swiftc")
        line("ok" if swiftc else "optional", "swiftc (Apple compilers)",
             "builds the PDF/image reader and the Apple model helper" if swiftc else "run: xcode-select --install")
        line("info", "macOS version", platform.mac_ver()[0] + " (Apple's on-device model needs 26 or later)")
    else:
        for name, why in (("pdftotext", "reads the text in PDFs"), ("tesseract", "reads text in images and scans")):
            line("ok" if shutil.which(name) else "optional", name, why)
    print("\nYou need Python, Claude Code, and one way to run a model on this computer: LM Studio or Ollama with a model\n"
          "loaded, or Apple's on-device model on macOS 26 or later. The rest is optional.")


if __name__ == "__main__":
    main()
