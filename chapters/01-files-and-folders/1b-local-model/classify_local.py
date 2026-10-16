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
import argparse
import json
import re
import subprocess
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


def read_head(path: Path, limit: int = 2000) -> str:
    # PDFs and images: let the on-device helper pull out text (PDF text layer, or OCR for
    # scans and screenshots). Without the helper we fall back to raw bytes, so PDFs and
    # images are judged by filename only.
    if path.suffix.lower() in EXTRACT_SUFFIXES and HELPER.exists():
        try:
            done = subprocess.run([str(HELPER), str(path), str(limit)],
                                  capture_output=True, text=True, timeout=60)
            if done.returncode == 0 and done.stdout.strip():
                return done.stdout[:limit]
        except (subprocess.TimeoutExpired, OSError):
            pass
    with path.open("rb") as handle:  # read only the start, never the whole file
        data = handle.read(limit)
    if b"\x00" in data:
        return f"[binary file, {path.stat().st_size} bytes]"
    return data.decode("utf-8", errors="replace")


def classify(base_url: str, model: str, name: str, head: str) -> dict:
    body = {
        "model": model,
        "temperature": 0,
        "max_tokens": 200,
        # Reasoning models (Gemma 4, Qwen3...) otherwise spend the whole token budget
        # "thinking" and return an empty answer. This is a simple lookup, so turn it off.
        "reasoning_effort": "none",
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"File name: {name}\n\nContent start:\n{head}"},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "classification", "strict": True, "schema": SCHEMA},
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
    print(f"Wrote {out} ({len(results)} of {len(files)} files labelled)")


if __name__ == "__main__":
    main()
