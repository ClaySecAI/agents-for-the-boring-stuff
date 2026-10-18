"""Create a fake, messy Downloads folder to practice on.

    python make_mess.py [target_dir] [--with-project]   (default: ./practice/downloads)

Every file is tiny and contains a plain-text description of what it
pretends to be, so the agent can learn about it by reading, the same way
it would with a real file's contents.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FILES = {
    # photos and screenshots
    "IMG_2041.jpg": "[pretend JPEG] photo of a dog at the beach",
    "IMG_2042.jpg": "[pretend JPEG] photo of a sunset",
    "Screenshot 2026-03-02 at 9.14.07 AM.png": "[pretend PNG] screenshot of a calendar",
    "Screenshot 2026-03-02 at 9.15.31 AM.png": "[pretend PNG] screenshot of an error dialog",
    "logo_final_v3.png": "[pretend PNG] company logo",
    # documents
    "invoice_march.pdf": "[pretend PDF] Invoice #1043, Acme Plumbing, $240.00",
    "invoice_march (1).pdf": "[pretend PDF] Invoice #1043, Acme Plumbing, $240.00",
    "lease_scan_0042.pdf": "[pretend PDF] Residential lease agreement, 12 months",
    "resume_final_v3.docx": "[pretend DOCX] Resume of Jordan Lee, software developer",
    "meeting_notes.docx": "[pretend DOCX] Notes from Q1 planning meeting",
    "tax_form_w2.pdf": "[pretend PDF] W-2 wage and tax statement 2025",
    # spreadsheets and data
    "budget_2026.xlsx": "[pretend XLSX] household budget, monthly categories",
    "export (3).csv": "customer_id,name,total\n1,Ana,40\n2,Bo,15\n",
    "export (4).csv": "customer_id,name,total\n1,Ana,40\n2,Bo,15\n",
    "sales_q1.csv": "region,units\nnorth,120\nsouth,98\n",
    # installers and archives
    "python-3.12.2-macos11.pkg": "[pretend installer] Python installer package",
    "Zoom.dmg": "[pretend installer] Zoom disk image",
    "project_backup.zip": "[pretend ZIP] archive of old project files",
    "photos_2024.tar.gz": "[pretend archive] compressed photo set",
    # text and misc
    "todo.txt": "buy groceries\ncall landlord\nrenew passport\n",
    "notes.txt": "ideas: a small CLI for renaming files; maybe a newsletter?\n",
    "untitled.txt": "asdf asdf test test",
    "a.txt": "",
    "scan_0007.pdf": "[pretend PDF] could be a receipt or a letter, unclear",
    "document(2).docx": "[pretend DOCX] draft of a cover letter",
    "random.bin": "[pretend binary] unknown data",
    # a nested file the agent should not miss
    "old_stuff/readme_old.txt": "These are old files from my previous laptop.\n",
    "old_stuff/IMG_1001.jpg": "[pretend JPEG] photo from a birthday party",
}


# With --with-project: a nested project folder, like the ones that pile up in a real
# Downloads. It exists to exercise top-level mode, where this whole folder moves as one item.
PROJECT_FILES = {
    "some-project/README.md": "# some-project\nA small sample project.\n",
    "some-project/src/app.py": "print('hello')\n",
    "some-project/src/util/helpers.py": "def add(a, b):\n    return a + b\n",
    "some-project/data/notes.txt": "sample data file\n",
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target", nargs="?", type=Path, default=Path("practice/downloads"))
    ap.add_argument("--with-project", action="store_true", help="also add a nested project folder")
    args = ap.parse_args()
    files = dict(FILES)
    if args.with_project:
        files.update(PROJECT_FILES)
    target = args.target
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} already exists and is not empty. Delete it or pick another path.")
    for name, content in files.items():
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    print(f"Created {len(files)} files in {target}")


if __name__ == "__main__":
    main()
