#!/usr/bin/env python3
"""
Generate a CROS-style Table of Contents PDF from three CSV sources.

Usage:
    python create_table_contents.py <sessions.csv> <compliance.csv> <papers_data.csv> <output.pdf>

Arguments:
    sessions.csv   - Session schedule: defines session groupings and paper IDs.
                     Paper titles here are matched against FORM TITLE in compliance.csv.
    compliance.csv - Compliance report: canonical PDF title and author list per paper.
    results.csv    - Page mapping: starting page number per paper (by zero-padded PDF name).
    output.pdf     - Destination path for the generated PDF.
"""

from __future__ import annotations

import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.lib.pagesizes import letter
from reportlab.lib.pagesizes import legal
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit


# ---------------------------------------------------------------------------
# Page geometry
# ---------------------------------------------------------------------------

PAGE_W, PAGE_H = letter

LEFT_MARGIN   = 56
TOP_MARGIN    = 48
BOTTOM_MARGIN = 40

TITLE_X      = PAGE_W / 2
TITLE_TOP_Y  = PAGE_H - 60
MAIN_TITLE_Y = PAGE_H - 110
SUBTITLE_Y   = PAGE_H - 158

CONTENT_LEFT  = 62
CONTENT_RIGHT = PAGE_W - 44
CONTENT_WIDTH = CONTENT_RIGHT - CONTENT_LEFT

# Safe split widths to prevent text from overflowing past CONTENT_RIGHT.
# Authors are indented 16 pt, so their budget is narrower than titles.
TITLE_TEXT_WIDTH  = CONTENT_WIDTH - 6
AUTHOR_TEXT_WIDTH = CONTENT_WIDTH - 22   # 16 pt indent + 6 pt safety buffer

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

SESSION_HEADER_FONT = ("Times-Bold",   11.5)
TITLE_FONT          = ("Times-Roman",  10.5)
AUTHOR_FONT         = ("Times-Italic", 9)
PRELIM_FONT         = ("Times-Roman",  12)
PRELIM_RIGHT_X      = PAGE_W - 58

# ---------------------------------------------------------------------------
# Misc constants
# ---------------------------------------------------------------------------

FOOTER_START_PAGE = 14   # first page carries roman numeral "xiv"

# Minimum dot leaders needed to keep the page number on the same line as the
# last title fragment. Fewer => page number is pushed to its own line.
MIN_LEADER_DOTS = 2

# Word-overlap ratio threshold for fuzzy title matching (0-1).
FUZZY_MATCH_THRESHOLD = 0.60


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PaperEntry:
    title:       str
    authors:     str
    paper_id:    Optional[str] = None
    page_number: str = ""


@dataclass
class SessionBlock:
    header: str
    papers: List[PaperEntry] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_spaces(text: str) -> str:
    """Collapse runs of whitespace into a single space and strip the string."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(text: str) -> str:
    """Return a lowercase, whitespace-normalised string for title matching."""
    return normalize_spaces(text).lower()


def word_overlap_score(a: str, b: str) -> float:
    """Return the Jaccard word-overlap ratio between two normalised strings.

    Used for fuzzy title matching when an exact lookup fails.
    """
    words_a = set(re.findall(r"[a-z0-9]+", a))
    words_b = set(re.findall(r"[a-z0-9]+", b))
    if not words_a or not words_b:
        return 0.0
    return len(words_a & words_b) / max(len(words_a), len(words_b))


def strip_author_initials(name: str) -> str:
    """Remove single-letter abbreviations (e.g. 'M.', 'A.') from one author name.

    Example: 'Jose M. A. Joao' -> 'Jose Joao'
    """
    tokens = normalize_spaces(name).split()
    return " ".join(t for t in tokens if not re.fullmatch(r"[A-Za-z]\.", t))


def format_authors(raw: str) -> str:
    """Format the PDF AUTHORS field from the compliance CSV for display.

    Authors arrive comma-separated in 'First [Initials] Last' order.
    Only middle-name initials are stripped; order and separators are kept.

    Example: 'Jose M. A. Joao, Maria B. Silva' -> 'Jose Joao, Maria Silva'
    """
    return ", ".join(
        strip_author_initials(a.strip())
        for a in raw.split(",")
        if a.strip()
    )


def clean_session_header(raw: str) -> str:
    """Extract a compact session label from the verbose schedule string.

    Input:  'S28M1  |  Terca - 08:30 as 10:30 - Sala 1: Multi-robot Systems I. Chair: X'
    Output: 'S28M1 | Multi-robot Systems I.'
    """
    raw = normalize_spaces(raw)
    if "|" not in raw:
        return raw

    left, right = raw.split("|", 1)
    code = normalize_spaces(left)

    right = re.sub(r".*?Sala\s*\d+\s*:\s*", "", right, flags=re.IGNORECASE)
    right = re.sub(r"\s*Chair:.*$",          "", right, flags=re.IGNORECASE)
    right = normalize_spaces(right)

    return f"{code} | {right}" if right else code


# ---------------------------------------------------------------------------
# CSV loaders
# ---------------------------------------------------------------------------

def load_compliance_data(path: Path) -> Dict[str, Tuple[str, str]]:
    """Load the compliance CSV and index entries by normalised FORM TITLE.

    Returns a dict { norm_form_title: (pdf_title, formatted_authors) }
    ready for exact or fuzzy lookup during session parsing.
    """
    data: Dict[str, Tuple[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            form_title  = normalize_spaces(row.get("FORM TITLE",  ""))
            pdf_title   = normalize_spaces(row.get("PDF TITLE",   ""))
            pdf_authors = normalize_spaces(row.get("PDF AUTHORS", ""))
            if not form_title:
                continue
            data[normalize_key(form_title)] = (
                pdf_title or form_title,
                format_authors(pdf_authors),
            )
    return data


def lookup_compliance(
    session_title: str,
    compliance: Dict[str, Tuple[str, str]],
) -> Tuple[Optional[Tuple[str, str]], bool]:
    """Look up a paper in the compliance dict by title.

    Tries an exact normalised match first; falls back to the best fuzzy
    (Jaccard word-overlap) match above FUZZY_MATCH_THRESHOLD.

    Returns (result_tuple_or_None, was_fuzzy_match).
    """
    key = normalize_key(session_title)

    if key in compliance:
        return compliance[key], False

    best_score, best_key = 0.0, None
    for ck in compliance:
        score = word_overlap_score(key, ck)
        if score > best_score:
            best_score, best_key = score, ck

    if best_key and best_score >= FUZZY_MATCH_THRESHOLD:
        return compliance[best_key], True

    return None, False


def load_page_numbers(path: Path) -> Dict[int, str]:
    """Load the results CSV and return { paper_id_int: start_page_str }.

    The 'pdf' column contains zero-padded filenames like '052.pdf'; the stem
    is converted to int (52) to match the numeric Paper ID in the sessions CSV.
    """
    pages: Dict[int, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pagina = row.get("#_first_page", "").strip()
            print(pagina)
            try:
                pages[int(Path(row.get("cmt_id", "")).stem)] = pagina
            except ValueError:
                print("error")
                continue
    return pages


def parse_sessions(
    sessions_path: Path,
    compliance:    Dict[str, Tuple[str, str]],
    pages:         Dict[int, str],
) -> List[SessionBlock]:
    """Parse the sessions CSV and assemble SessionBlock objects.

    The sessions CSV drives structure (order and grouping of sessions/papers).
    For each paper the canonical title and authors are fetched from the
    compliance dict (exact match, then fuzzy fallback); page numbers come from
    the pages dict. Papers not found in compliance are included with a warning,
    using the session-CSV title as a fallback.
    """
    sessions: List[SessionBlock] = []
    current:  Optional[SessionBlock] = None

    with sessions_path.open("r", encoding="utf-8-sig", newline="") as f:
        for raw_row in csv.reader(f):
            row    = [c.strip() for c in raw_row]
            first  = row[0] if len(row) > 0 else ""
            second = row[1] if len(row) > 1 else ""
            third  = row[2] if len(row) > 2 else ""
            fourth = row[3] if len(row) > 3 else ""

            if not any(row):
                continue
            if first.startswith("CROS 2026") or first == "Sessao" or first == "Sessão":
                continue

            # Session header row: first cell starts with 'S', other cells empty.
            if first.startswith("S") and not second and not third and not fourth:
                current = SessionBlock(header=clean_session_header(first))
                sessions.append(current)
                continue

            # Paper row: must have at least a paper ID in the second column.
            if current is None or not second:
                continue

            paper_id    = second
            form_title  = normalize_spaces(third)
            pid_int     = int(paper_id) if paper_id.isdigit() else -1
            page_number = pages.get(pid_int, "")

            result, was_fuzzy = lookup_compliance(form_title, compliance)

            if result:
                pdf_title, authors = result
                if was_fuzzy:
                    print(f"  [fuzzy match] paper {paper_id}: '{form_title[:60]}'")
            else:
                print(f"  [no match]    paper {paper_id}: '{form_title[:60]}'")
                pdf_title, authors = form_title, ""

            if not pdf_title:
                continue

            current.papers.append(PaperEntry(
                title       = pdf_title,
                authors     = authors,
                paper_id    = paper_id,
                page_number = page_number,
            ))

    return sessions


# ---------------------------------------------------------------------------
# Roman numerals
# ---------------------------------------------------------------------------

def roman_numeral(n: int) -> str:
    """Convert a positive integer to a lowercase Roman numeral string."""
    vals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100,  "c"), (90,  "xc"), (50,  "l"), (40,  "xl"),
        (10,   "x"), (9,   "ix"), (5,   "v"), (4,   "iv"), (1, "i"),
    ]
    out = []
    for val, sym in vals:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


# ---------------------------------------------------------------------------
# PDF drawing primitives
# ---------------------------------------------------------------------------

def draw_centered(c: canvas.Canvas, text: str, y: float,
                  font_name: str, font_size: float) -> None:
    """Draw horizontally centred text at the given y coordinate."""
    c.setFont(font_name, font_size)
    c.drawCentredString(TITLE_X, y, text)


def draw_prelim_list(c: canvas.Canvas) -> None:
    """Draw the fixed preliminary-pages list (title page, copyright, etc.)."""
    items = [
        ("Title Page 1",                     "i"),
        ("Title Page 2",                     "ii"),
        ("Copyright Notice",                 "iii"),
        ("Acknowledgments",                  "iv"),
        ("Messagem from the General Chair",  "v"),
        ("Messagem from the Program Chairs", "vii"),
        ("Committees",                       "viii"),
        ("Table of Contents",                "xiv"),
    ]
    y = PAGE_H - 262
    c.setFont(*PRELIM_FONT)
    for label, page in items:
        c.drawString(58, y, label)
        c.drawRightString(PRELIM_RIGHT_X, y, page)
        y -= 28


def draw_footer(c: canvas.Canvas, page_index: int) -> None:
    """Draw a centred roman-numeral page number at the bottom of the page."""
    c.setFont("Times-Roman", 11)
    c.drawCentredString(PAGE_W / 2, 20, roman_numeral(page_index))


def draw_session_header(c: canvas.Canvas, header: str, y: float) -> float:
    """Draw a bold session header and return the new y position below it."""
    c.setFont(*SESSION_HEADER_FONT)
    for line in simpleSplit(header, SESSION_HEADER_FONT[0], SESSION_HEADER_FONT[1], CONTENT_WIDTH):
        c.drawString(LEFT_MARGIN, y, line)
        y -= 13
    return y


def split_title_lines(title: str) -> List[str]:
    """Wrap a paper title to fit within TITLE_TEXT_WIDTH."""
    return simpleSplit(title, TITLE_FONT[0], TITLE_FONT[1], TITLE_TEXT_WIDTH)


def split_author_lines(authors: str) -> List[str]:
    """Wrap an author string to fit within AUTHOR_TEXT_WIDTH."""
    return simpleSplit(authors, AUTHOR_FONT[0], AUTHOR_FONT[1], AUTHOR_TEXT_WIDTH)


def estimate_entry_height(entry: PaperEntry) -> float:
    """Estimate the vertical space (pts) needed to render one paper entry.

    Adds an extra line when the page number cannot fit beside the last
    title fragment and must occupy a dedicated dot-leader line.
    """
    title_lines  = split_title_lines(entry.title)
    author_lines = split_author_lines(entry.authors) if entry.authors else []

    extra = 0
    if entry.page_number and title_lines:
        last_w = stringWidth(title_lines[-1], TITLE_FONT[0], TITLE_FONT[1])
        dot_w  = stringWidth(".", TITLE_FONT[0], TITLE_FONT[1])
        pn_w   = stringWidth(entry.page_number, "Times-Roman", 11) + 10
        dot_x  = CONTENT_LEFT + last_w + 8
        end_x  = CONTENT_RIGHT - 2 - pn_w
        n      = max(0, int((end_x - dot_x) / dot_w)) if (end_x > dot_x and dot_w > 0) else 0
        if n < MIN_LEADER_DOTS:
            extra = 14

    return len(title_lines) * 14 + (len(author_lines) * 10 if author_lines else 0) + 8 + extra


def draw_title_with_leaders(
    c: canvas.Canvas,
    title_lines: Sequence[str],
    y: float,
    page_number: str = "",
) -> float:
    """Draw wrapped title lines with dot leaders and an optional page number.

    If there is room for at least MIN_LEADER_DOTS dots after the last title
    fragment, the page number is placed on the same line. Otherwise it is
    pushed to a new line filled entirely with dots from the left margin.

    Returns the y coordinate immediately below the last drawn line.
    """
    if not title_lines:
        return y

    c.setFont(*TITLE_FONT)
    line_height = 12

    for line in title_lines[:-1]:
        c.drawString(CONTENT_LEFT, y, line)
        y -= line_height

    last  = title_lines[-1]
    dot_w = stringWidth(".", TITLE_FONT[0], TITLE_FONT[1])
    dot_x = CONTENT_LEFT + stringWidth(last, TITLE_FONT[0], TITLE_FONT[1]) + 8

    c.drawString(CONTENT_LEFT, y, last)

    if page_number:
        pn_w  = stringWidth(page_number, "Times-Roman", 11) + 10
        end_x = CONTENT_RIGHT - 2 - pn_w
        n     = max(0, int((end_x - dot_x) / dot_w)) if (end_x > dot_x and dot_w > 0) else 0

        if n >= MIN_LEADER_DOTS:
            # Enough room: dots + page number on the same line as the title.
            c.drawString(dot_x, y, "." * n)
            c.setFont("Times-Roman", 11)
            c.drawRightString(CONTENT_RIGHT, y, page_number)
        else:
            # Title too long: page number moves to a dedicated line of dots.
            y    -= line_height
            end_x = CONTENT_RIGHT - 2 - pn_w
            n_new = max(0, int((end_x - CONTENT_LEFT) / dot_w)) if (end_x > CONTENT_LEFT and dot_w > 0) else 0
            c.setFont(*TITLE_FONT)
            if n_new > 0:
                c.drawString(CONTENT_LEFT, y, "." * n_new)
            c.setFont("Times-Roman", 11)
            c.drawRightString(CONTENT_RIGHT, y, page_number)
    else:
        # No page number: fill the remainder of the line with dots.
        end_x = CONTENT_RIGHT - 2
        if end_x > dot_x and dot_w > 0:
            n = max(0, int((end_x - dot_x) / dot_w))
            if n > 0:
                c.drawString(dot_x, y, "." * n)

    return y - line_height


def draw_authors(c: canvas.Canvas, authors: str, y: float) -> float:
    """Draw author names in italic, indented 16 pt below the title.

    Returns the y coordinate immediately below the last author line.
    """
    if not authors:
        return y
    c.setFont(*AUTHOR_FONT)
    for line in split_author_lines(authors):
        c.drawString(CONTENT_LEFT + 16, y, line)
        y -= 9
    return y


# ---------------------------------------------------------------------------
# PDF renderer
# ---------------------------------------------------------------------------

def render_pdf(sessions: List[SessionBlock], output_path: Path) -> None:
    """Render the complete Table of Contents PDF from a list of SessionBlocks."""
    if not sessions:
        raise ValueError("No sessions to render.")

    c = canvas.Canvas(str(output_path), pagesize=letter)
    c.setTitle("CROS 2026 - Table of Contents")
    c.setSubject("Generated from CSV")
    c.setCreator("ReportLab")

    page_index = FOOTER_START_PAGE

    # ---- First page: cover header + preliminary list + start of content ----
    draw_centered(c, "2026 Conference on Robotics (CROS)", TITLE_TOP_Y, "Times-Roman", 15)
    draw_centered(c, "CROS 2026",         MAIN_TITLE_Y, "Times-Bold",  28)
    draw_centered(c, "Table of Contents", SUBTITLE_Y,   "Times-Roman", 20)
    draw_prelim_list(c)

    y = 308
    draw_centered(c, "Conference on Robotics", y, "Times-Roman", 16)
    y -= 46

    for session in sessions:
        # Page break if the session header + at least one paper will not fit.
        first_h = estimate_entry_height(session.papers[0]) if session.papers else 0
        if y < BOTTOM_MARGIN + 48 + first_h:
            draw_footer(c, page_index)
            c.showPage()
            page_index += 1
            y = PAGE_H - TOP_MARGIN

        y = draw_session_header(c, session.header, y)
        y -= 10

        for paper in session.papers:
            if y < BOTTOM_MARGIN + estimate_entry_height(paper):
                draw_footer(c, page_index)
                c.showPage()
                page_index += 1
                y = PAGE_H - TOP_MARGIN
                # Repeat session header on continuation pages.
                y = draw_session_header(c, session.header, y)
                y -= 8

            y = draw_title_with_leaders(c, split_title_lines(paper.title), y, paper.page_number)
            y = draw_authors(c, paper.authors, y)
            y -= 8    # spacing between paper entries

        y -= 9        # extra gap between sessions

    draw_footer(c, page_index)
    c.save()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Sequence[str]) -> int:
    if len(argv) != 5:
        print(f"Usage: {Path(argv[0]).name} "
              "<sessions.csv> <compliance.csv> <papers_data.csv> <output.pdf>")
        return 1

    sessions_path   = Path(argv[1]).expanduser().resolve()
    compliance_path = Path(argv[2]).expanduser().resolve()
    results_path    = Path(argv[3]).expanduser().resolve()
    output_path     = Path(argv[4]).expanduser().resolve()

    for p in (sessions_path, compliance_path, results_path):
        if not p.is_file():
            print(f"Error: file not found: {p}")
            return 1

    print("Loading compliance data...")
    compliance = load_compliance_data(compliance_path)

    print("Loading page numbers...")
    pages = load_page_numbers(results_path)

    print("Parsing sessions...")
    sessions = parse_sessions(sessions_path, compliance, pages)

    total_papers = sum(len(s.papers) for s in sessions)
    print(f"Rendering PDF ({total_papers} papers across {len(sessions)} sessions)...")

    try:
        render_pdf(sessions, output_path)
    except Exception as exc:
        print(f"Error generating PDF: {exc}")
        return 1

    print(f"PDF written to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
