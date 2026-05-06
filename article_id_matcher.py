"""
Article ID Matcher (Script 3)
=============================
Author: LASER Laboratory (Adapted)
Description: Scans a folder of PDFs, extracts their titles, and matches them 
against the official copyright database to retrieve the ARTICLE IDENTIFIER.

Key Features:
- Lean Extraction: Only parses the PDF for the title using font-size heuristics.
- Smashed Matching: Agnostic to spacing and PDF encoding errors.
- Duplicate Handling: Always fetches the latest (lowest) ID in the spreadsheet.
- Occurrence Counter: Adds a 'MATCH COUNT' column for duplicate tracking.
- Smart CLI: Requires explicit arguments or displays a helpful usage example.
"""

import argparse
import difflib
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import pdfplumber

# ---------------------------------------------------------------------------
# Text Normalization & Encoding Repair
# ---------------------------------------------------------------------------

def fix_pdf_encoding(text: str) -> str:
    """Corrects broken encoding sequences common in PDF text extraction."""
    t = text.lower()
    mapping = [
        ("a˜", "ao"), ("o˜", "ao"), ("c¸", "c"), ("a´", "a"), ("e´", "e"),
        ("i´", "i"), ("o´", "o"), ("u´", "u"), ("´i", "i"), ("´a", "a"),
        ("´e", "e"), ("´o", "o"), ("´u", "u"), ("˜a", "a"), ("˜o", "o")
    ]
    for broken, fixed in mapping:
        t = t.replace(broken, fixed)
    return t

def normalize_title(text: str) -> str:
    """Standardizes titles using the 'Smashed Matching' technique."""
    if pd.isna(text): return ""
    t = fix_pdf_encoding(str(text))
    # Decompose unicode characters and strip non-alphabetic symbols
    n = unicodedata.normalize("NFKD", t).encode("ASCII", "ignore").decode("utf-8")
    n = re.sub(r"[^a-z\s]", "", n)
    # Remove all spaces to make comparison immune to PDF spacing errors
    return n.replace(" ", "")

# ---------------------------------------------------------------------------
# PDF Title Extraction Logic
# ---------------------------------------------------------------------------

def _group_into_lines(words: list, tolerance: float = 3) -> list:
    """Groups coordinate-based words into logical horizontal lines."""
    if not words: return []
    lines = []
    current_line = [words[0]]
    current_top = words[0]["top"]

    for w in words[1:]:
        if abs(w["top"] - current_top) <= tolerance:
            current_line.append(w)
        else:
            current_line.sort(key=lambda x: x["x0"])
            lines.append(current_line)
            current_line = [w]
            current_top = w["top"]

    if current_line:
        current_line.sort(key=lambda x: x["x0"])
        lines.append(current_line)
    return lines

def extract_pdf_title(pdf_path: Path) -> str:
    """Extracts the title from a PDF based on the largest font size."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages: return ""
            page = pdf.pages[0]
            words = page.extract_words(extra_attrs=["size", "fontname"])
            if not words: return ""
            
            # Restrict search to the top 50% of the page
            valid_words = [w for w in words if w.get("top", 0) < page.height * 0.5]
            if not valid_words: valid_words = words
            
            valid_sizes = sorted(set(round(w.get("size", 0), 1) for w in valid_words if w.get("size", 0) > 0), reverse=True)
            if not valid_sizes: return ""
            
            title_size = valid_sizes[0]
            largest_words = [w for w in valid_words if round(w.get("size", 0), 1) == title_size]
            
            # If the largest font is just a tiny header, fallback to the second largest
            if len(largest_words) <= 3 and len(valid_sizes) > 1:
                average_top = sum(w.get("top", 0) for w in largest_words) / len(largest_words)
                if average_top < page.height * 0.08:
                    title_size = valid_sizes[1]
            
            title_words = [w for w in words if round(w.get("size", 0), 1) == title_size and w.get("top", 0) < page.height * 0.45]
            title_words.sort(key=lambda w: (round(w["top"]), w["x0"]))
            
            title_lines = _group_into_lines(title_words, tolerance=3)
            title = " ".join(" ".join(w["text"] for w in line) for line in title_lines)
            
            # Clean up hyphens and extra spaces
            title = re.sub(r"-\s+", "", title)
            title = re.sub(r"\s+", " ", title).strip()
            title = re.sub(r"^\d+\s+", "", title).strip("*")
            
            if title and len(title) > 10:
                return title
            
            # Fallback: Extract pure text and take the first few lines
            text = page.extract_text(layout=False) or ""
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            return " ".join(lines[:4])

    except Exception as e:
        print(f"Error reading {pdf_path.name}: {e}")
        return ""

# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

def process_directory(folder_path: Path, copyright_path: Path, output_path: Path):
    """Processes all PDFs, matches titles, and generates the final report."""
    if not folder_path.exists():
        print(f"\n[ERROR] The directory '{folder_path}' does not exist.")
        sys.exit(1)
        
    pdfs = sorted(folder_path.rglob("*.pdf"))
    if not pdfs:
        print(f"\n[ERROR] No PDFs found in directory: '{folder_path}'")
        sys.exit(1)

    print(f"Loading database: {copyright_path.name}...")
    try:
        df_cpy = pd.read_excel(copyright_path)
    except FileNotFoundError:
        print(f"\n[ERROR] Database file '{copyright_path}' not found.")
        sys.exit(1)
    
    results = []
    print(f"Processing {len(pdfs)} PDFs...")

    for pdf_path in pdfs:
        pdf_title = extract_pdf_title(pdf_path)
        if not pdf_title:
            pdf_title = "[Title Extraction Failed]"
            
        pdf_title_smashed = normalize_title(pdf_title)
        
        best_id = "artigo não encontrado"
        best_score = -1.0
        match_count = 0

        # Iterate through the copyright database to find the best title match
        for _, c_row in df_cpy.iterrows():
            c_title = str(c_row.get("ARTICLE TITLE", ""))
            c_title_smashed = normalize_title(c_title)
            
            # Calculate similarity ratio
            score = difflib.SequenceMatcher(None, pdf_title_smashed, c_title_smashed).ratio()
            
            # Count any valid match (score >= 75%)
            if score >= 0.75:
                match_count += 1
                
                # Use ">=" to ensure that if a duplicate title appears lower in the sheet 
                # it overwrites the older occurrence.
                if score >= best_score:
                    best_score = score
                    best_id = str(c_row.get("ARTICLE IDENTIFIER", "artigo não encontrado"))

        # Append exactly the three required columns
        results.append({
            "ARTICLE TITLE": pdf_title,
            "ARTICLE IDENTIFIER": best_id,
            "MATCH COUNT": match_count
        })
        
        status = "OK" if best_id != "artigo não encontrado" else "NOT FOUND"
        print(f"[{status}] {pdf_path.name} -> {best_id} (Matches: {match_count})")

    # Generate the final output file
    df_results = pd.DataFrame(results)
    df_results.to_excel(output_path, index=False)
    print(f"\nSuccessfully generated {len(results)} records in: {output_path.name}")

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extracts PDF titles and matches them to retrieve the correct Article ID.",
        epilog="""
Example of use:
  python script3_article_id_matcher.py --folder "02 - PDF Artigos Programacao" --copyright "SearchCopyright.xlsx" --output "article_ids.xlsx"
  
If no arguments are provided, the script will show this help message.
""",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Required parameters (None of them have 'default' values anymore)
    parser.add_argument("--folder", help="Directory containing the PDF files.", required=False)
    parser.add_argument("--copyright", help="Official copyright database (Excel file).", required=False)
    
    # Optional parameter with a default
    parser.add_argument("--output", default="article_ids.xlsx", help="Output filename (default: article_ids.xlsx).")
    
    args = parser.parse_args()

    # Log message and abort if required arguments are missing
    if not args.folder or not args.copyright:
        print("\n[LOG] Missing required arguments.")
        print("You must specify both the PDF folder and the Copyright spreadsheet.\n")
        print("Example:")
        print('  python script3_article_id_matcher.py --folder "02 - PDF Artigos Programacao" --copyright "SearchCopyright_3.xlsx"\n')
        sys.exit(1)

    process_directory(Path(args.folder), Path(args.copyright), Path(args.output))