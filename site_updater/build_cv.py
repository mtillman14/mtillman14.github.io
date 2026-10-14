#!/usr/bin/env python
"""Build the CV (moderncv, classic/blue) from the site's markdown files.

Every CV entry comes from a YAML file or the YAML front matter of a Jekyll
collection, so the website and the CV share one source of truth:

    _cv_text/objective.md          Opening paragraph (markdown body, no front matter)
    _data/cv/education/            Education
    _data/cv/research_positions/   Research Positions
    _teaching/                     Teaching
    _publications/                 Peer-Reviewed Publications      (category: manuscripts)
                                   Peer-Reviewed Conference Papers (category: conferences)
    _talks/                        Conference Abstracts            (default)
                                   Additional Presentations        (type: Seminar, or cv_section: additional)
    _data/cv/leadership/           Leadership
    _data/cv/service/              Service
    _data/cv/awards/               Awards
    _data/cv/certificates/         Certificates
    _data/cv/affiliations/         Professional Affiliations

The _data/cv/ files are also available to Jekyll as site.data.cv.<section>.
Files whose names start with "_" are skipped, matching Jekyll's convention.

All text is plain text: every LaTeX special character is escaped, so don't
write LaTeX in the data files. The objective also supports **bold** and *italic*.

Usage (from the site_updater/ folder, like the other scripts):
    python build_cv.py

Writes site_updater/cv/build/cv.tex. If latexmk is installed, it also compiles
the PDF and copies it to files/cv.pdf. Requires: jinja2, pyyaml.
"""

import datetime
import re
import shutil
import subprocess
from pathlib import Path

import jinja2
import yaml

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = Path(__file__).resolve().parent / "cv"
BUILD_DIR = TEMPLATE_DIR / "build"

# Name to bold in author lists and presenter fields
HIGHLIGHT = re.compile(r"\bTillman,?\s+M\b\.?")

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
SEASONS = {"spr": 3, "sum": 6, "fall": 9, "win": 12}
# How each talk "type" is described in the CV
PRESENTATION_LABELS = {"Poster": "Poster presentation", "Podium": "Podium presentation"}
DEGREES = {"PhD", "MS", "MSc", "MD", "PT", "DPT", "ME", "MEng", "BS", "BA", "MA", "PT PhD"}


# ---------- reading ----------

def read_front_matter(path):
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.match(r"---\n(.*?)\n---", text, re.S)
    return yaml.safe_load(match.group(1)) if match else {}


def read_collection(folder):
    """Entries from a Jekyll collection (front matter of *.md) or a _data folder (*.yml)."""
    entries = []
    for path in sorted((ROOT / folder).glob("*.md")) + sorted((ROOT / folder).glob("*.yml")):
        if path.name.startswith("_"):
            continue
        if path.suffix == ".yml":
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        else:
            data = read_front_matter(path)
        data["_file"] = path.name
        entries.append(data)
    return sorted(entries, key=sort_key, reverse=True)


def read_text(name):
    return (ROOT / "_cv_text" / f"{name}.md").read_text(encoding="utf-8").strip()


# ---------- dates ----------

def entry_date(entry):
    """The entry's date as a datetime.date or a free-text string like '2019-2024'."""
    return entry.get("date", entry.get("dates"))


def sort_key(entry):
    """Most recent first: by start year, then end year ('Present' = ongoing), then month.
    A year-only date borrows month/day from a dated file name."""
    value = entry_date(entry)
    if isinstance(value, datetime.date):
        return (value.year, value.year, value.month, value.day)
    text = str(value or "")
    years = [int(y) for y in re.findall(r"\d{4}", text)]
    start = min(years, default=0)
    end = 9999 if "present" in text.lower() else max(years, default=0)
    word = re.match(r"[A-Za-z]+", text)
    if word:
        word = word.group(0).lower()
        month = MONTHS.get(word[:3]) or SEASONS.get(word[:4]) or SEASONS.get(word[:3]) or 0
        return (start, end, month, 0)
    from_name = re.match(r"(\d{4})-(\d{2})-(\d{2})", entry.get("_file", ""))
    if from_name and int(from_name.group(1)) == start:
        return (start, end, int(from_name.group(2)), int(from_name.group(3)))
    return (start, end, 0, 0)


def cvdate(value, fmt="%b %Y"):
    """Format a date for the left-hand column; free-text dates pass through."""
    if isinstance(value, datetime.date):
        return value.strftime(fmt)
    return "" if value is None else str(value)


def year(value):
    """Start year as text: 2024-10-01 -> '2024', '2019-2024' -> '2019'."""
    if isinstance(value, datetime.date):
        return str(value.year)
    years = re.findall(r"\d{4}", str(value or ""))
    return min(years) if years else ""


def year_label(entry, previous=None):
    """Left-column year, left blank when it repeats the entry above."""
    label = year(entry_date(entry))
    if isinstance(previous, dict) and year(entry_date(previous)) == label:
        return ""
    return label


# ---------- authors ----------

def abbreviate(name):
    """'Nicole C. Veit' -> 'Veit NC'. Names already like 'Hirsch ZM' are kept."""
    name = re.sub(r"^and\s+", "", name.strip())
    if re.fullmatch(r"[\w'-]+ [A-Z]{1,3}", name):
        return name
    parts = name.replace(".", " ").split()
    if len(parts) < 2:
        return name
    initials = "".join(p[0].upper() for p in parts[:-1])
    return f"{parts[-1]} {initials}"


def pub_authors(entry):
    """Abbreviated author list from 'authors' (written by pubsFromBib.py, or by hand)."""
    raw = entry.get("authors")
    if not raw:
        return ""
    names = [n.strip() for n in raw.split(",")]
    names = [n for n in names if n and n not in DEGREES]
    return ", ".join(abbreviate(n) for n in names)


# ---------- LaTeX filters ----------

LATEX_SPECIAL = {
    "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "&": r"\&", "%": r"\%", "$": r"\$",
    "#": r"\#", "_": r"\_", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}


def latex(value):
    """Escape plain text for LaTeX."""
    if value is None:
        return ""
    return "".join(LATEX_SPECIAL.get(c, c) for c in str(value).strip())


def url(value):
    """Escape a URL for use inside \\href{...}: only % and # need it."""
    return str(value).replace("%", r"\%").replace("#", r"\#")


def sentence(text):
    """End with a period unless the text already ends in . ? or !"""
    return text if text.endswith((".", "?", "!")) else text + "."


def highlight(text):
    return HIGHLIGHT.sub(lambda m: rf"\textbf{{{m.group(0)}}}", text)


def markdown(text):
    """Minimal markdown -> LaTeX: **bold**, *italic*."""
    text = latex(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", text)
    return re.sub(r"\*(.+?)\*", r"\\textit{\1}", text)


# ---------- main ----------

def main():
    talks = read_collection("_talks")
    for talk in talks:
        talk.setdefault("presenter", (talk.get("authors") or "").split(",")[0].strip())
    is_additional = lambda t: t.get("cv_section") == "additional" or t.get("type") == "Seminar"

    publications = read_collection("_publications")
    for pub in publications:
        pub["author_list"] = pub_authors(pub)

    context = {
        "name": yaml.safe_load((ROOT / "_config.yml").read_text(encoding="utf-8"))["name"],
        "objective": read_text("objective"),
        "education": read_collection("_data/cv/education"),
        "research_positions": read_collection("_data/cv/research_positions"),
        "teaching": read_collection("_teaching"),
        "publications": [p for p in publications if p.get("category", "manuscripts") == "manuscripts"],
        "conference_papers": [p for p in publications if p.get("category") == "conferences"],
        "abstracts": [t for t in talks if not is_additional(t)],
        "additional_presentations": [t for t in talks if is_additional(t)],
        "leadership": read_collection("_data/cv/leadership"),
        "service": read_collection("_data/cv/service"),
        "awards": read_collection("_data/cv/awards"),
        "certificates": read_collection("_data/cv/certificates"),
        "affiliations": read_collection("_data/cv/affiliations"),
    }

    # LaTeX-friendly delimiters: ((* block *)), ((( variable ))), ((= comment =))
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(TEMPLATE_DIR),
        block_start_string="((*", block_end_string="*))",
        variable_start_string="(((", variable_end_string=")))",
        comment_start_string="((=", comment_end_string="=))",
        trim_blocks=True, lstrip_blocks=True,
    )
    env.filters.update(latex=latex, url=url, highlight=highlight, sentence=sentence, markdown=markdown, cvdate=cvdate, year=year)
    env.globals["entry_date"] = entry_date
    env.globals["year_label"] = year_label
    env.globals["presentation_label"] = lambda kind: PRESENTATION_LABELS.get(kind, "Oral presentation")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    tex_path = BUILD_DIR / "cv.tex"
    tex_path.write_text(env.get_template("cv.tex.j2").render(**context), encoding="utf-8")
    print(f"Wrote {tex_path.relative_to(ROOT)}")

    if shutil.which("latexmk") is None:
        print("latexmk not found: compile cv.tex yourself (e.g. upload it to Overleaf).")
        return
    subprocess.run(["latexmk", "-pdf", "-interaction=nonstopmode", "cv.tex"], cwd=BUILD_DIR, check=True)
    shutil.copy(BUILD_DIR / "cv.pdf", ROOT / "files" / "cv.pdf")
    print("Copied PDF to files/cv.pdf")


if __name__ == "__main__":
    main()
