"""Assign files to your projects by MEANING, with a small embedding model. No text is generated.

    python3 embed_assign.py <folder> <projects.json> [options]

An embedding model turns a piece of text into a list of numbers so that texts with similar meaning
get similar numbers. This script embeds each project (its name and description) and each file (its
name, download website and the start of its contents), then gives the file to the project whose
description it is closest to. If nothing is close enough, or two projects are nearly tied, the file
goes to Unsorted.

Compared with the text-generating model in assign_projects.py:

  * it is far smaller and faster (a model of 80 to 600 MB, and a second or two for a whole folder)
  * it cannot write anything, so it cannot leak anything through its output
  * it cannot judge sensitivity, so every file is labelled "unknown" (the most cautious label) unless
    you merge in labels from another pass
  * it can learn from examples without any training: give it files you have already sorted with
    --examples and it will treat them as extra descriptions of their projects

Options:
  --base-url URL       OpenAI-compatible server (default LM Studio, http://localhost:1234/v1)
  --model NAME         embedding model identifier (default: embedder)
  --preset NAME        prompt format the model expects: nomic (default), embeddinggemma, qwen3, none
  --threshold X        least similarity to accept a project (default 0.0, meaning always take the best)
  --margin X           least gap between the best and second-best project (default 0.0)
  --examples FILE      JSON list of {"project": name, "path": file path relative to <folder>}
  --top-level          only the folder's direct files; hidden files are skipped
  --no-source          hide the download website
  --out FILE           where to write assignments.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
CH1 = HERE.parent
sys.path.insert(0, str(CH1))
sys.path.insert(0, str(CH1 / "1b-local-model"))
sys.path.insert(0, str(HERE))
import assign_projects as assign  # noqa: E402
import classify_local as local  # noqa: E402

UNSORTED = assign.UNSORTED

# How each model family wants its inputs framed. A project description plays the "query", a file the "document".
PRESETS = {
    "nomic": ("search_query: ", "search_document: "),
    "embeddinggemma": ("task: search result | query: ", "title: none | text: "),
    "qwen3": ("Instruct: Given a project description, find the documents that belong to that project\nQuery: ", ""),
    "none": ("", ""),
}


def embed(base_url: str, model: str, texts: list[str], batch: int = 16) -> list[list[float]]:
    """Unit-length vectors, so a dot product is a cosine similarity."""
    vectors: list[list[float]] = []
    for start in range(0, len(texts), batch):
        body = json.dumps({"model": model, "input": texts[start:start + batch]}).encode()
        request = urllib.request.Request(f"{base_url}/embeddings", body, {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=300) as response:
            rows = sorted(json.load(response)["data"], key=lambda r: r["index"])
        for row in rows:
            vec = row["embedding"]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            vectors.append([x / norm for x in vec])
    return vectors


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def decide(scores: dict[str, float], threshold: float, margin: float) -> str:
    """The project with the highest similarity, or Unsorted if it is too weak or too close to call."""
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if not ranked:
        return UNSORTED
    best_name, best = ranked[0]
    second = ranked[1][1] if len(ranked) > 1 else -1.0
    if best < threshold or (best - second) < margin:
        return UNSORTED
    return best_name


def file_text(path: Path, rel: str, use_source: bool, head: int = 1500) -> str:
    domain = assign.download_domain(path) if use_source else None
    lines = [f"File name: {path.name}"]
    if domain:
        lines.append(f"Downloaded from: {domain}")
    lines.append(local.read_head(path, head))
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("folder", type=Path)
    ap.add_argument("projects", type=Path)
    ap.add_argument("--base-url", default="http://localhost:1234/v1")
    ap.add_argument("--model", default="embedder")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="nomic")
    ap.add_argument("--threshold", type=float, default=0.0)
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--examples", type=Path)
    ap.add_argument("--top-level", action="store_true")
    ap.add_argument("--no-source", action="store_true")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    if not args.folder.is_dir():
        sys.exit(f"Not a folder: {args.folder}")

    projects = assign.load_projects(args.projects)
    names = [p["name"] for p in projects]
    query_prefix, doc_prefix = PRESETS[args.preset]

    candidates = args.folder.iterdir() if args.top_level else args.folder.rglob("*")
    files = sorted(p for p in candidates if p.is_file() and p.name != ".DS_Store"
                   and not (args.top_level and p.name.startswith(".")))

    # Each project is described by its own text plus any example files you have sorted into it.
    project_texts = [(p["name"], f"{p['name']}. {p.get('description', '')}".strip()) for p in projects]
    examples = json.loads(args.examples.read_text()) if args.examples else []
    example_texts = []
    for item in examples:
        if item["project"] in names and (args.folder / item["path"]).is_file():
            example_texts.append((item["project"], file_text(args.folder / item["path"], item["path"], not args.no_source)))

    texts = [query_prefix + t for _n, t in project_texts] + [doc_prefix + t for _n, t in example_texts]
    texts += [doc_prefix + file_text(p, str(p.relative_to(args.folder)), not args.no_source) for p in files]
    vectors = embed(args.base_url, args.model, texts)

    owners = [n for n, _t in project_texts] + [n for n, _t in example_texts]
    project_vecs = vectors[:len(owners)]
    file_vecs = vectors[len(owners):]

    results = {}
    for path, vec in zip(files, file_vecs):
        best: dict[str, float] = {}
        for owner, pvec in zip(owners, project_vecs):
            best[owner] = max(best.get(owner, -1.0), dot(vec, pvec))
        results[str(path.relative_to(args.folder))] = {
            "primary": decide(best, args.threshold, args.margin),
            "also": [],
            "sensitivity": "unknown",  # an embedding model cannot judge this; "unknown" is the cautious label
        }
    out = args.out or args.folder.resolve().parent / "assignments-embed.json"
    out.write_text(json.dumps(results, indent=2))
    unsorted = sum(1 for v in results.values() if v["primary"] == UNSORTED)
    print(f"Wrote {out.name}: {len(results)} files, {unsorted} unsorted "
          f"(model {args.model}, preset {args.preset}, threshold {args.threshold}, margin {args.margin}).")


if __name__ == "__main__":
    main()
