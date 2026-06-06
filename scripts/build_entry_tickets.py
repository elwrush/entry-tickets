"""build_entry_tickets.py — Generate personalised entry ticket PDFs for a class.

Queries Supabase classlists table for all students in a given class,
generates a Typst file with one page per student (header, demographics,
7-row answer table), and compiles to a single PDF.

Usage:
    python scripts/build_entry_tickets.py M3-4A [--output-dir output]

Requires env vars: SUPABASE_URL, SUPABASE_ESL_KEY
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "templates"
OUTPUT_DIR = PROJECT_ROOT / "output"
ROBOTO_FONT_DIR = Path(
    os.path.expandvars(r"%APPDATA%\TinyTeX\texmf-dist\fonts\opentype\google\roboto")
)
LOGO_FILES = ["ACT.png", "cambridge.png"]


def fetch_students_by_class(class_name: str, exclude: set = set()) -> list[dict]:
    import requests

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_ESL_KEY")
    if not url or not key:
        print("ERROR: SUPABASE_URL and SUPABASE_ESL_KEY env vars must be set")
        sys.exit(1)

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    r = requests.get(
        f"{url}/rest/v1/classlists",
        headers=headers,
        params={"class": f"eq.{class_name}"},
    )
    r.raise_for_status()
    students = r.json()

    if exclude:
        students = [s for s in students if (s.get("name") or "") not in exclude]

    if not students:
        print(f"No students found for class {class_name}")
        sys.exit(1)

    students.sort(key=lambda s: (s.get("name", "") or "").lower())
    return students


# ---------------------------------------------------------------------------
# Typst content builder
# ---------------------------------------------------------------------------

HEADER_TYP = r"""#set text(font: "Roboto", size: 11pt)
#set page(paper: "a4", margin: 2cm)

"""


def build_student_page(student: dict) -> str:
    class_name = student.get("class", "")
    student_id = student.get("student_id", "")
    name = student.get("name", "")

    return f"""#block(
  stroke: (bottom: 0.5pt + black),
  inset: (bottom: 6pt),
  grid(
    columns: (1fr, 2fr, 1fr),
    align: (left + horizon, center + horizon, right + horizon),
    image("ACT.png", height: 1.2cm),
    text(size: 16pt, weight: "bold")[Mathayom Program],
    image("cambridge.png", height: 1.6cm),
  )
)
#v(6pt)
#align(center, text(size: 14pt, weight: "bold")[ENTRY TICKET])
#v(6pt)
#line(length: 100%, stroke: 0.5pt + black)
#v(12pt)

#grid(
  columns: (auto, 1fr, auto, 1fr, auto, 1fr),
  column-gutter: 4pt,
  align: bottom,
  [*CLASS:*], [{class_name}],
  [*ID:*],    [{student_id}],
  [*NAME:*],  [{name}],
)
#v(12pt)

#table(
  columns: (2cm, 1fr),
  align: (center, left),
  rows: (2cm, 2cm, 2cm, 2cm, 2cm, 2cm, 2cm),
  stroke: 0.5pt,
  align(center + horizon, [*1*]), [],
  align(center + horizon, [*2*]), [],
  align(center + horizon, [*3*]), [],
  align(center + horizon, [*4*]), [],
  align(center + horizon, [*5*]), [],
  align(center + horizon, [*6*]), [],
  align(center + horizon, [*7*]), [],
)
"""


def build_typ_content(students: list[dict]) -> str:
    lines = [HEADER_TYP]
    for i, student in enumerate(students):
        if i > 0:
            lines.append("#pagebreak()\n")
        lines.append(build_student_page(student))
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Compilation
# ---------------------------------------------------------------------------

def compile_typ(typ_path: Path, output_pdf: Path) -> bool:
    cmd = [
        "typst",
        "compile",
        str(typ_path),
        str(output_pdf),
        "--font-path",
        str(ROBOTO_FONT_DIR),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            print(f"Typst compile failed (exit {result.returncode}):")
            print(result.stderr)
            return False
        print(f"PDF created: {output_pdf}")
        return True
    except subprocess.TimeoutExpired:
        print("Error: Typst compile timed out")
        return False
    except FileNotFoundError:
        print("Error: Typst CLI not found.")
        return False


def copy_logos(dst_dir: Path) -> list[Path]:
    copied = []
    for name in LOGO_FILES:
        src = TEMPLATES_DIR / name
        dst = dst_dir / name
        if src.exists():
            shutil.copy2(src, dst)
            copied.append(dst)
    return copied


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    class_name = sys.argv[1]
    output_dir = OUTPUT_DIR
    if len(sys.argv) >= 4 and sys.argv[2] == "--output-dir":
        output_dir = Path(sys.argv[3])

    print(f"Fetching students for class {class_name}...")
    exclude = set()
    for i, arg in enumerate(sys.argv):
        if arg == "--exclude" and i + 1 < len(sys.argv):
            exclude = set(x.strip() for x in sys.argv[i + 1].split(","))
            break
    students = fetch_students_by_class(class_name, exclude)
    print(f"  Found {len(students)} student(s)")

    print("Building Typst content...")
    typ_content = build_typ_content(students)

    output_dir.mkdir(parents=True, exist_ok=True)
    typ_path = output_dir / f"{class_name}-entry-tickets.typ"
    pdf_path = output_dir / f"{class_name}-entry-tickets.pdf"

    typ_path.write_text(typ_content, encoding="utf-8")
    print(f"  Typst source: {typ_path}")

    copied = copy_logos(output_dir)
    print("  Copied logo images")

    print("Compiling to PDF...")
    success = compile_typ(typ_path, pdf_path)

    for f in copied:
        try:
            f.unlink()
        except Exception:
            pass

    print("Done." if success else "Failed.")


if __name__ == "__main__":
    main()
