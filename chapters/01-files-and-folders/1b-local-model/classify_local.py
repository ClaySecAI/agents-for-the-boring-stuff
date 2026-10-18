"""Classify files with a model running on YOUR machine (LM Studio, Ollama, ...).

    python classify_local.py <folder> [--base-url URL] [--model NAME]

Talks to any OpenAI-compatible local server. Defaults match LM Studio:
    --base-url http://localhost:1234/v1      (Ollama: http://localhost:11434/v1)

File contents go to the local server only. Nothing leaves your machine.

The model can only answer with values from two fixed lists (a JSON schema with
enums, enforced by the server's constrained decoding). So there is no
free-text field for file contents to leak through. Output: classification.json
beside <folder>, ready for make_plan.py.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

CATEGORIES = ["Documents", "Images", "Spreadsheets", "Installers", "Archives", "Text", "Review"]
SENSITIVITIES = ["none", "personal", "financial", "health", "credentials", "government_id", "legal"]

SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "sensitivity": {"type": "string", "enum": SENSITIVITIES},
    },
    "required": ["category", "sensitivity"],
    "additionalProperties": False,
}

SYSTEM = f"""You classify one file at a time for a file-tidying tool.
You get the file name and the first part of its content.
Answer with JSON: a category and a sensitivity.

category, by what the file IS (not only its extension): {", ".join(CATEGORIES)}.
Use Review when you cannot tell, or the file is empty or meaningless.

sensitivity, data-loss-prevention view: what kind of sensitive data the file holds.
none = nothing sensitive. personal = resumes, contact details, private letters.
financial = invoices, bank, tax, budgets. health = medical. credentials = passwords, keys.
government_id = SSN, passport, tax IDs, W-2. legal = leases, contracts.
If unsure whether something is sensitive, pick the sensitive kind, not none."""


HELPER = Path(__file__).resolve().parent.parent / "extract_text"  # built from extract_text.swift
EXTRACT_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".tif", ".tiff", ".gif", ".bmp", ".webp"}


def _run(cmd: list[str], timeout: int = 60) -> str:
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return ""
    return done.stdout if done.returncode == 0 else ""


def extract_text(path: Path, limit: int) -> str:
    """Text from a PDF or image, or "" when no extractor is available.

    macOS: the Swift helper (PDFKit text layer, Vision OCR). Anywhere else, the same two steps
    with open-source tools if they are installed: pdftotext (poppler) for the text layer of a PDF,
    and tesseract for OCR on images and on PDFs that turn out to be scans (pdftoppm renders a page).
    Missing tools are skipped, never an error: the file is then judged by name and extension alone."""
    suffix = path.suffix.lower()
    if suffix not in EXTRACT_SUFFIXES:
        return ""
    if HELPER.exists():
        text = _run([str(HELPER), str(path), str(limit)])
        if text.strip():
            return text
    if suffix == ".pdf":
        if shutil.which("pdftotext"):
            text = _run(["pdftotext", "-l", "3", "-q", str(path), "-"])
            if text.strip():
                return text
        if shutil.which("pdftoppm") and shutil.which("tesseract"):
            with tempfile.TemporaryDirectory() as tmp:
                _run(["pdftoppm", "-r", "150", "-f", "1", "-l", "1", "-png", str(path), f"{tmp}/page"])
                for image in sorted(Path(tmp).glob("page*.png")):
                    return _run(["tesseract", str(image), "-", "-l", "eng"], timeout=120)
        return ""
    if shutil.which("tesseract"):
        return _run(["tesseract", str(path), "-", "-l", "eng"], timeout=120)
    return ""


def read_head(path: Path, limit: int = 2000) -> str:
    # PDFs and images go through extract_text(). Without any extractor we fall back to raw
    # bytes, so PDFs and images are judged by filename only.
    if path.suffix.lower() in EXTRACT_SUFFIXES:
        text = extract_text(path, limit)
        if text.strip():
            return text[:limit]
    with path.open("rb") as handle:  # read only the start, never the whole file
        data = handle.read(limit)
    if b"\x00" in data:
        return f"[binary file, {path.stat().st_size} bytes]"
    return data.decode("utf-8", errors="replace")


def classify(base_url: str, model: str, name: str, head: str,
             system: str | None = None, schema: dict | None = None, user: str | None = None,
             max_tokens: int = 200) -> dict:
    """Ask the local model for JSON that matches `schema`. The defaults are this chapter's own
    classification; Chapter 2 passes its own system prompt, schema and user message."""
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": max_tokens,
        # Reasoning models (Gemma 4, Qwen3...) otherwise spend the whole token budget
        # "thinking" and return an empty answer. This is a simple lookup, so turn it off.
        "reasoning_effort": "none",
        "messages": [
            {"role": "system", "content": system or SYSTEM},
            {"role": "user", "content": user or f"File name: {name}\n\nContent start:\n{head}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "classification", "strict": True, "schema": schema or SCHEMA},
        },
    }
    req = urllib.request.Request(
        f"{base_url}/chat/completions", json.dumps(body).encode(),
        {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        text = json.load(resp)["choices"][0]["message"]["content"]
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()  # reasoning models
    return json.loads(text)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("folder", type=Path)
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="classifier")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--top-level", action="store_true",
                    help="only the folder's direct files; subfolders are never opened")
    args = ap.parse_args()
    if not args.folder.is_dir():
        raise SystemExit(f"Not a folder: {args.folder}")

    out = args.out or args.folder.resolve().parent / "classification.json"
    results = {}
    candidates = args.folder.iterdir() if args.top_level else args.folder.rglob("*")
    files = sorted(p for p in candidates if p.is_file() and p.name != ".DS_Store")
    for i, path in enumerate(files, 1):
        rel = str(path.relative_to(args.folder))
        try:
            results[rel] = classify(args.base_url, args.model, path.name, read_head(path))
        except Exception as err:  # fail closed: make_plan treats a missing label as sensitive + Review
            print(f"  ! {rel}: {err}")
            continue
        print(f"[{i}/{len(files)}] {rel}: {results[rel]['category']} / {results[rel]['sensitivity']}")
    out.write_text(json.dumps(results, indent=2))
    print(f"Wrote {out} ({len(results)} of {len(files)} files labeled)")


if __name__ == "__main__":
    main()
