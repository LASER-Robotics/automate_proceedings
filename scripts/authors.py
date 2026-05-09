#!/usr/bin/env python3
"""
Build an author index from a compliance CSV.

For every unique author found in the PDF AUTHORS column, the output CSV
contains one row with the formatted author name and a semicolon-separated
list of the papers they contributed to (from PDF TITLE).

Name formatting rules:
  - 'First [Middles] Last'  →  'Last, First [Initials]'
  - Middle names are abbreviated to their first letter (e.g. 'Silva' → 'S.')
  - Middle initials already in 'X.' form are kept as-is
  - Particles (da, de, do, dos, das, van, von, …) are dropped

Examples:
  'João Maria'           →  'Maria, João'
  'Ana J. J. Maria'      →  'Maria, Ana J. J.'
  'José da Silva Barbosa'→  'Barbosa, José S.'

Usage:
    python3 authors.py <final_compliance_report.csv> <output.csv>
"""

from __future__ import annotations

import csv
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set
import argparse


# Lowercase connective particles that are dropped from the middle of a name.
PARTICLES: Set[str] = {
    "da", "de", "do", "dos", "das",
    "van", "von", "del", "di", "du",
    "der", "den", "des", "al", "el",
    "bin", "ibn", "la", "le", "e",
}

# Names whose token count exceeds this are assumed to be malformed data
# (e.g. two authors merged without a comma separator) and are skipped.
MAX_NAME_TOKENS = 7


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def normalize_spaces(text: str) -> str:
    """Collapse runs of whitespace into a single space and strip the string."""
    return re.sub(r"\s+", " ", text).strip()


def looks_like_institution(name: str) -> bool:
    """Return True if the string appears to be a place or institution rather
    than a person's name (e.g. 'Embraer S.A.', 'Ouro Preto').

    Detection heuristics (any one is sufficient):
    - Contains 'S.A.' or 'Ltda'
    - Ends with a period and has no capital letter in the last word
    - All words are lowercase (city/country names)
    """
    if re.search(r"\bS\.A\.\b|\bLtda\b", name, re.IGNORECASE):
        return True
    tokens = name.split()
    if all(t[0].islower() for t in tokens if t):
        return True
    # A single period at the end that is not an initial suggests a sentence.
    if name.endswith(".") and not re.search(r"[A-Z]\.$", name):
        return True
    return False


def clean_raw_author(raw: str) -> str:
    """Strip common trailing artefacts left by footnote superscripts.

    Example: 'Paulo L. J. Drews-Jr 1 .'  →  'Paulo L. J. Drews-Jr'
    """
    # Remove trailing whitespace, isolated digits, and stray periods.
    return normalize_spaces(re.sub(r"[\s\d.]+$", "", raw.rstrip()))


# ---------------------------------------------------------------------------
# Name formatting
# ---------------------------------------------------------------------------

def format_author_name(name: str) -> Optional[str]:
    """Convert 'First [Middles] Last' to 'Last, First [Initials]'.

    Returns None if the name is unrecognisable (institution, too many tokens,
    or empty after cleaning).
    """
    name = normalize_spaces(name)
    if not name:
        return None

    if looks_like_institution(name):
        return None

    tokens = name.split()

    if len(tokens) > MAX_NAME_TOKENS:
        print(f"  [skipped — too many tokens] '{name}'")
        return None

    if len(tokens) == 1:
        return tokens[0]   # single-token name, return as-is

    last  = tokens[-1]
    first = tokens[0]
    middles = tokens[1:-1]

    # Build the middle-initial string.
    initials: List[str] = []
    for token in middles:
        low = token.lower()
        if low in PARTICLES:
            continue                                        # drop particle
        if re.fullmatch(r"[A-Za-z]\.", token):
            initials.append(token)                          # keep existing initial
        elif token:
            initials.append(token[0].upper() + ".")        # abbreviate

    formatted = f"{last}, {first}"
    if initials:
        formatted += " " + " ".join(initials)
    return formatted


# ---------------------------------------------------------------------------
# Compliance CSV parsing
# ---------------------------------------------------------------------------

def split_raw_authors(raw: str) -> List[str]:
    """Split the PDF AUTHORS field into individual raw author strings.

    The primary separator is a comma, but some records use an isolated digit
    (footnote superscript) as an additional separator between names.
    """
    # First split on commas.
    parts = raw.split(",")

    # Then split each part on isolated digits (e.g. ' 1 ' between two names).
    result: List[str] = []
    for part in parts:
        sub_parts = re.split(r"\s+\d+\s+", part)
        result.extend(sub_parts)

    return result


def build_author_index(compliance_path: Path) -> Dict[str, List[str]]:
    """Parse the compliance CSV and return { formatted_author: [paper_title, …] }.

    Each author is mapped to the list of PDF titles they appear in, deduped
    and order-preserved per paper.
    """
    # Use a dict of sets to avoid duplicates per author.
    author_papers: Dict[str, Set[str]] = defaultdict(set)

    with compliance_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            pdf_title   = normalize_spaces(row.get("PDF TITLE",   ""))
            pdf_authors = normalize_spaces(row.get("PDF AUTHORS", ""))

            if not pdf_title or not pdf_authors:
                continue

            for raw in split_raw_authors(pdf_authors):
                cleaned = clean_raw_author(raw)
                if not cleaned:
                    continue

                formatted = format_author_name(cleaned)
                if formatted:
                    author_papers[formatted].add(pdf_title)

    return author_papers


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    output_folder = "./reports/"
    parser = argparse.ArgumentParser(description="Build an author index from a compliance CSV.")
    parser.add_argument("--compliance_report", default="final_compliance_report.csv", help="Name of the compliance csv from sort_pdf_schedule.py")
    parser.add_argument("--output", default="authors.csv", help="Name of the output csv file")
    args = parser.parse_args()

    compliance_path = Path(output_folder + args.compliance_report)
    output_path     = Path(output_folder + args.output)

    if not compliance_path.is_file():
        print(f"Error: file not found: {compliance_path}")
        return 1

    print("Building author index...")
    author_papers = build_author_index(compliance_path)

    # Sort authors alphabetically by their formatted name.
    sorted_authors = sorted(author_papers.keys(), key=lambda n: n.lower())

    print(f"Writing {len(sorted_authors)} authors to {output_path}...")
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["author", "papers"])
        for author in sorted_authors:
            papers_str = "; ".join(sorted(author_papers[author]))
            writer.writerow([author, papers_str])

    print(f"Done. Output written to: {output_path}")
    return 0

if __name__ == "__main__":
    main()