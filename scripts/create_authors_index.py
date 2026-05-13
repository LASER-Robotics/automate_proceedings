#!/usr/bin/env python3
"""Generate an Author Index PDF from author and paper CSV files.

Usage:
    python create_authors_index.py <authors.csv> <papers_data.csv> <output.pdf>

Input CSVs:
    - authors.csv: contains one author per row and a semicolon-separated list
      of paper titles written by that author.
    - papers_data.csv: contains the paper titles and the page where each paper
      starts (matched against the `titulo_artigo` column).

The output follows the visual structure of the provided AuthorIndex.pdf as
closely as possible: centered title, two-column alphabetical author list,
dotted leaders, and page footer numbering.
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple
import argparse
import pandas as pd

from reportlab.lib.pagesizes import A4, letter
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = letter

# Visual tuning based on the provided AuthorIndex.pdf.
TITLE_Y = PAGE_H - 72
TITLE_FONT = ("Times-Bold", 24)
ENTRY_FONT = ("Times-Roman", 11)
FOOTER_FONT = ("Times-Roman", 11)

LEFT_COL_X = 58
RIGHT_COL_X = 305
PAGE_NUMBER_RIGHT_X = 265
RIGHT_COL_NUMBER_RIGHT_X = 545
TOP_ENTRY_Y = PAGE_H - 108
BOTTOM_MARGIN = 56
LINE_STEP = 18.8
ROWS_PER_PAGE = 34
FOOTER_PAGE_START = 633
DOT_CHAR = "."
MIN_DOTS = 2


@dataclass(frozen=True)
class AuthorEntry:
    """One author and the set of page numbers where the author's papers appear."""

    author: str
    pages: Tuple[int, ...]


def normalize_spaces(text: str) -> str:
    """Collapse repeated whitespace and trim the result."""
    return re.sub(r"\s+", " ", text or "").strip()


def normalize_key(text: str) -> str:
    """Generate a comparison/sort key that ignores accents, case and spacing."""
    text = normalize_spaces(text).lower()
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_page_number(value: str) -> int | None:
    """Convert a page value to an integer when possible."""
    value = normalize_spaces(value)
    if not value:
        return None
    m = re.search(r"\d+", value)
    return int(m.group()) if m else None


def load_paper_pages(papers_csv: Path) -> Dict[str, int]:
    """Load the paper start page for each paper title from the results CSV."""
    mapping: Dict[str, int] = {}

    with papers_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = normalize_spaces(row.get("title_pdf", ""))
            page = parse_page_number(row.get("#_first_page", ""))
            if title and page is not None:
                mapping[normalize_key(title)] = page

    return mapping


def load_authors(authors_csv: Path) -> List[Tuple[str, List[str]]]:
    """Load author-to-papers relationships from the authors CSV."""
    rows: List[Tuple[str, List[str]]] = []

    with authors_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            author = normalize_spaces(row.get("author", ""))
            papers_field = normalize_spaces(row.get("papers", ""))
            if not author or not papers_field:
                continue
            papers = [normalize_spaces(p) for p in papers_field.split(";") if normalize_spaces(p)]
            rows.append((author, papers))

    return rows


def build_author_index(authors_csv: Path, papers_csv: Path) -> Tuple[List[AuthorEntry], List[str]]:
    """Cross-reference authors with paper pages and build the final index rows."""
    paper_pages = load_paper_pages(papers_csv)
    authors_rows = load_authors(authors_csv)

    pages_by_author: Dict[str, List[int]] = defaultdict(list)
    warnings: List[str] = []

    for author, papers in authors_rows:
        for paper in papers:
            page = paper_pages.get(normalize_key(paper))
            if page is None:
                warnings.append(f"Warning: paper title not found in results CSV: {paper}")
                continue
            if page not in pages_by_author[author]:
                pages_by_author[author].append(page)

    entries: List[AuthorEntry] = []
    for author in sorted(pages_by_author.keys(), key=lambda a: normalize_key(a)):
        pages = tuple(sorted(pages_by_author[author]))
        entries.append(AuthorEntry(author=author, pages=pages))

    return entries, warnings


def roman_numeral(n: int) -> str:
    """Convert an integer into a lower-case Roman numeral."""
    vals = [
        (1000, "m"), (900, "cm"), (500, "d"), (400, "cd"),
        (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
        (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i"),
    ]
    out: List[str] = []
    for val, sym in vals:
        while n >= val:
            out.append(sym)
            n -= val
    return "".join(out)


def draw_footer(c: canvas.Canvas, page_number: int) -> None:
    """Draw the centered page number in the footer."""
    c.setFont(*FOOTER_FONT)
    c.drawCentredString(PAGE_W / 2, 20, str(page_number))


def dots_for_line(author: str, pages_text: str, column_right_x: float, dot_x: float) -> int:
    """Return the maximum number of dots that fits before the page numbers."""
    pages_w = stringWidth(pages_text, ENTRY_FONT[0], ENTRY_FONT[1])
    dot_w = stringWidth(DOT_CHAR, ENTRY_FONT[0], ENTRY_FONT[1])

    page_start_x = column_right_x - pages_w
    available = page_start_x - 4 - dot_x
    if dot_w <= 0 or available <= 0:
        return 0
    return int(available / dot_w)


def entry_line_count(author: str, pages: Tuple[int, ...], x: float, right_x: float) -> int:
    """Return 1 if the entry fits on one line, 2 if it needs a continuation line."""
    pages_text = ", ".join(str(p) for p in pages)
    author_w = stringWidth(author, ENTRY_FONT[0], ENTRY_FONT[1])
    pages_w  = stringWidth(pages_text, ENTRY_FONT[0], ENTRY_FONT[1])
    dot_w    = stringWidth(DOT_CHAR, ENTRY_FONT[0], ENTRY_FONT[1])
    dot_x    = x + author_w + 9
    end_x    = right_x - pages_w - 4
    available = int((end_x - dot_x) / dot_w) if (end_x > dot_x and dot_w > 0) else 0
    return 1 if available >= MIN_DOTS else 2


def draw_entry(c: canvas.Canvas, author: str, pages: Tuple[int, ...], x: float, right_x: float, y: float) -> int:
    """Draw one author entry with dotted leaders and right-aligned page numbers.

    If the author name and page numbers do not fit on a single line, the author
    name is drawn with dots filling to the right margin, and the page numbers
    are placed on a continuation line below (also preceded by dots).

    Returns the number of lines consumed (1 or 2).
    """
    pages_text = ", ".join(str(p) for p in pages)

    c.setFont(*ENTRY_FONT)
    author_w = stringWidth(author, ENTRY_FONT[0], ENTRY_FONT[1])
    pages_w  = stringWidth(pages_text, ENTRY_FONT[0], ENTRY_FONT[1])
    dot_w    = stringWidth(DOT_CHAR, ENTRY_FONT[0], ENTRY_FONT[1])
    dot_x    = x + author_w + 9
    end_x    = right_x - pages_w - 4
    available = int((end_x - dot_x) / dot_w) if (end_x > dot_x and dot_w > 0) else 0

    c.drawString(x, y, author)

    if available >= MIN_DOTS:
        # Everything fits: dots + page numbers on the same line.
        c.drawString(dot_x, y, DOT_CHAR * available)
        c.drawRightString(right_x, y, pages_text)
        return 1
    else:
        # Overflow: fill rest of line with dots, then page numbers on next line.
        fill = int((right_x - dot_x) / dot_w) if (right_x > dot_x and dot_w > 0) else 0
        if fill > 0:
            c.drawString(dot_x, y, DOT_CHAR * fill)

        y2     = y - LINE_STEP
        cont_x = x
        end_x2 = right_x - pages_w - 4
        fill2  = int((end_x2 - cont_x) / dot_w) if (end_x2 > cont_x and dot_w > 0) else 0
        if fill2 > 0:
            c.drawString(cont_x, y2, DOT_CHAR * fill2)
        c.drawRightString(right_x, y2, pages_text)
        return 2


def draw_title(c: canvas.Canvas) -> None:
    """Draw the centered Author Index title on the first page."""
    c.setFont(*TITLE_FONT)
    c.drawCentredString(PAGE_W / 2, TITLE_Y, "Author Index")


def render_pdf(entries: Sequence[AuthorEntry], output_pdf: Path, sorted_pdfs) -> None:
    """Render the author index PDF using a fixed two-column layout."""
    c = canvas.Canvas(str(output_pdf), pagesize=letter)
    c.setAuthor("OpenAI")
    c.setTitle("Author Index")
    c.setSubject("Generated from CSV files")
    c.setCreator("ReportLab")
    
    df = pd.read_csv(sorted_pdfs)    

    page_number = df['#_last_page'].iloc[-1] + 1
    idx = 0
    total = len(entries)
    first_page = True

    while idx < total:
        if first_page:
            draw_title(c)
        y = TOP_ENTRY_Y if not first_page else PAGE_H - 110

        # Fill the page in two columns, tracking y position per column so that
        # entries requiring two lines do not overlap with the next entry.
        left_start = idx
        left_y = y
        while idx < total:
            lines = entry_line_count(entries[idx].author, entries[idx].pages,
                                     LEFT_COL_X, PAGE_NUMBER_RIGHT_X)
            if left_y - lines * LINE_STEP < BOTTOM_MARGIN:
                break
            left_y -= lines * LINE_STEP
            idx += 1
        left_end = idx

        right_start = idx
        right_y = y
        while idx < total:
            lines = entry_line_count(entries[idx].author, entries[idx].pages,
                                     RIGHT_COL_X, RIGHT_COL_NUMBER_RIGHT_X)
            if right_y - lines * LINE_STEP < BOTTOM_MARGIN:
                break
            right_y -= lines * LINE_STEP
            idx += 1

        ly = y
        for i in range(left_start, left_end):
            e = entries[i]
            lines = draw_entry(c, e.author, e.pages, LEFT_COL_X, PAGE_NUMBER_RIGHT_X, ly)
            ly -= lines * LINE_STEP

        ry = y
        for i in range(right_start, idx):
            e = entries[i]
            lines = draw_entry(c, e.author, e.pages, RIGHT_COL_X, RIGHT_COL_NUMBER_RIGHT_X, ry)
            ry -= lines * LINE_STEP

        draw_footer(c, page_number)
        c.showPage()
        page_number += 1
        first_page = False

    c.save()


def main() -> int:
    output_folder = "./reports/"
    pdf_folder = "./proceedings_files/"
    parser = argparse.ArgumentParser(description="Build an author index from a compliance CSV.")
    parser.add_argument("--authors", default="authors.csv", help="Name of the compliance csv from sort_pdf_schedule.py")
    parser.add_argument("--sorted_pdfs", default="sorted_pdfs.csv", help="Name of the compliance csv from sort_pdf_schedule.py")
    parser.add_argument("--output", default="AuthorIndex.pdf", help="Name of the output csv file")
    args = parser.parse_args()

    authors_csv = Path(output_folder + args.authors)
    papers_csv = Path(output_folder + args.sorted_pdfs)

    df = pd.read_csv(papers_csv)
    page_number = df['proceedings_id'].iloc[-1]

    # tst = page_number.replace(".pdf", f"_{output_pdf}")
    autor_index_start_page = int(page_number.replace(".pdf", "")) + 1

    output_pdf = Path(pdf_folder + f"{autor_index_start_page}_" +  args.output)
    print(output_pdf)

    if not authors_csv.is_file():
        print(f"Error: file not found: {authors_csv}")
        return 1
    if not papers_csv.is_file():
        print(f"Error: file not found: {papers_csv}")
        return 1

    entries, warnings = build_author_index(authors_csv, papers_csv)
    for warning in warnings:
        print(warning)

    if not entries:
        print("Error: no author entries could be generated.")
        return 1

    render_pdf(entries, output_pdf, output_folder + args.sorted_pdfs)
    print(f"PDF generated at: {output_pdf}")
    return 0

# python create_authors_index.py <authors.csv> <papers_data.csv> <output.pdf>

if __name__ == "__main__":    
    main()
