"""
Usage:
    python3 pdf_metadata_extractor.py
    python3 pdf_metadata_extractor.py --folder "path/to/pdfs" --output extracted_articles.xlsx
"""

import re
import math
import argparse
from pathlib import Path

import pdfplumber
import openpyxl
from openpyxl.styles import Font

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Keywords indicating affiliation or sections — used to reject entire text lines
AFFILIATION_WORDS = {
    "university", "universidade", "universidad", "université",
    "institute", "instituto", "department", "departamento", "dept",
    "federal", "nacional", "national", "laboratory", "laboratório",
    "center", "centre", "centro", "school", "escola",
    "faculty", "faculdade", "college", "campus",
    "brazil", "brasil", "germany", "france", "portugal", "spain",
    "italy", "canada", "argentina", "algeria", "uruguay",
    "engineering", "engenharia", "science", "ciência", "ciencia",
    "technology", "tecnologia", "computing", "computação",
    "research", "pesquisa", "group", "grupo", "lab",
    "virtus", "ifsul", "usp", "ufrn", "ufmg", "ufpb", "ufam",
    "furg", "ufsm", "ufv", "ufcg", "ufscar", "ifro", "ifrn", "ufsc",
    "ufba", "ufla", "ufersa", "ufs", "upe", "ufpe",
    "unicamp", "coppe", "ifmg", "ita", "ime",
    "program", "programa", "graduate", "postgraduate",
    "pelotas", "manaus", "itacoatiara", "campina",
    "goiania", "goiânia", "brasilia", "brasília",
    "recife", "fortaleza", "salvador", "curitiba",
    "florianópolis", "florianopolis", "porto", "alegre", "belo",
    "horizonte", "vitória", "vitoria", "natal", "maceió", "maceio",
    "belém", "belem", "campinas", "blumenau", "aracaju",
    "amazonas", "pernambuco", "paraíba", "paraiba", "bahia",
    "sergipe", "parnamirim", "guanambi", "lavras",
    "montpellier", "lecce", "fray", "bentos", "kingston",
    "division", "divisão", "politecnico", "polytechnic",
    "aeronautica", "aeronautics", "av.", "rua",
    "systems", "sistemas", "email", "e-mail",
    "univ", "fed", "inst", "tech", "artificial", "intelligence", "inteligência", "inteligencia",
    "introduction", "introdução", "introducao", "abstract", "resumo"
}

# Compound terms commonly mistaken for person names
COMPOUND_BLOCKED_TERMS = {
    "rio grande", "santa maria", "sao paulo", "são paulo", "sa˜o paulo",
    "do norte", "do sul", "minas gerais", "mato grosso", "costa rica",
    "rio de janeiro", "fluminense", "joa˜o pessoa", "joão pessoa", "joão pessoa", 
    "sa˜o carlos-sp", "são carlos-sp", "são carlos-sp"
}

# Valid prepositions within names (must not trigger rejection)
NAME_PREPOSITIONS = {"da", "de", "do", "das", "dos", "e", "van", "von", "di", "del", "la", "le"}

# Regular Expressions
RE_EMAIL = re.compile(r"[\w\.\-\+]+@[\w\.\-]+\.\w+|\[\s*at\s*\]", re.IGNORECASE)
RE_ORCID = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dX]")
RE_SUPERSCRIPT_INLINE = re.compile(r"([A-ZÀ-ÿa-z])[\d\*†‡§∗¶#,]+(?:\s|$|,)")
RE_ORDINAL = re.compile(r"^\d+(st|nd|rd|th)$", re.IGNORECASE)
RE_ORDINAL_NUM = re.compile(r"^\d+$")
RE_ORDINAL_SUF = re.compile(r"^(st|nd|rd|th)$", re.IGNORECASE)
RE_NAME_TOKEN = re.compile(
    r"^[A-ZÀ-ŸV´Í][a-zA-ZÀ-ÿ´˜\-'`ı]{1,}(?:[\s\.]+[A-ZÀ-Ÿ]\.?)*(?:\s+[A-ZÀ-Ÿ][a-zA-ZÀ-ÿ\-'´˜ı]{1,})+$"
)

# ---------------------------------------------------------------------------
# Text Utilities
# ---------------------------------------------------------------------------

def clean_superscripts(text: str) -> str:
    """Removes numeric and symbolic superscripts attached to names."""
    text = re.sub(r"([A-ZÀ-ÿa-z\-])[\d\*†‡§∗¶#]+([,\s]|$)", r"\1\2", text)
    text = re.sub(r"\s+[\d\*†‡§∗¶#,]+$", "", text)
    return text.strip()

def is_email_or_orcid(line: str) -> bool:
    """Evaluates if the text string contains an email address or ORCID."""
    return bool(RE_EMAIL.search(line) or RE_ORCID.search(line))

def is_affiliation_line(line: str) -> bool:
    """Determines if the provided string constitutes an affiliation line."""
    if is_email_or_orcid(line):
        return True
    
    line_lower = line.lower()
    words = re.split(r"[\s,\.\-/]+", line_lower)
    
    for word in words:
        clean_word = re.sub(r"[^a-záàâãéèêíïóôõúüçñ]", "", word)
        if clean_word in AFFILIATION_WORDS and clean_word not in NAME_PREPOSITIONS:
            return True
            
    if re.match(r"^[A-Z][A-Z\s\-/\.]+$", line) and len(line) < 50:
        return True
        
    return False

def looks_like_name(text: str) -> bool:
    """Heuristic assessment to determine if a string resembles a person's name."""
    if not text or len(text) < 4:
        return False
    if is_email_or_orcid(text):
        return False
    if "@" in text or "http" in text.lower():
        return False

    text_lower = text.lower()
    for term in COMPOUND_BLOCKED_TERMS:
        if term in text_lower:
            return False

    words = text.split()
    if len(words) < 2 or len(words) > 8:
        return False

    first_char = text[0]
    if not (first_char.isupper() or first_char in "V´Í"):
        return False

    # Filter 1: Ensure no word constitutes a known affiliation
    for word in words:
        clean_word = re.sub(r"[^a-záàâãéèêíïóôõúüçñ]", "", word.lower())
        if clean_word in AFFILIATION_WORDS and clean_word not in NAME_PREPOSITIONS:
            return False

    # Filter 2: Enforce strict Title Case to block prose and descriptive text
    for word in words:
        clean_prefix = re.sub(r"^[^a-zA-ZÀ-ÿV´Í]+", "", word)
        if not clean_prefix:
            continue
        if clean_prefix.lower() in NAME_PREPOSITIONS:
            continue
        if not (clean_prefix[0].isupper() or clean_prefix[0] in "V´Í"):
            return False

    if all(c.isupper() or not c.isalpha() for c in text.replace(" ", "")):
        if len(text) < 20:
            return False

    long_words = [word for word in words if len(re.sub(r"[^a-záàâãéèêíïóôõúüçñ]", "", word.lower())) > 2]
    return bool(long_words)

# ---------------------------------------------------------------------------
# Strategy 1: Font and Position Extraction
# ---------------------------------------------------------------------------

def extract_by_font_and_position(pdf_path: Path):
    """
    Leverages pdfplumber to detect:
    - Title: identifies words featuring the largest font size.
    - Authors: isolates the text block situated between the title and the Abstract.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return None, None
            page = pdf.pages[0]

            words = page.extract_words(
                extra_attrs=["size", "fontname"],
                use_text_flow=False,
                keep_blank_chars=False,
            )

            if not words:
                return None, None

            sizes = sorted(
                set(round(w.get("size", 0), 1) for w in words if w.get("size", 0) > 0),
                reverse=True
            )

            if not sizes:
                return None, None

            page_height = page.height
            valid_words = [w for w in words if w.get("top", 0) < page_height * 0.5]

            if not valid_words:
                valid_words = words

            valid_sizes = sorted(
                set(round(w.get("size", 0), 1) for w in valid_words if w.get("size", 0) > 0),
                reverse=True
            )

            if not valid_sizes:
                return None, None

            title_size = valid_sizes[0]

            largest_words = [w for w in valid_words if round(w.get("size", 0), 1) == title_size]
            if len(largest_words) <= 3 and len(valid_sizes) > 1:
                average_top = sum(w.get("top", 0) for w in largest_words) / len(largest_words)
                if average_top < page_height * 0.08:
                    title_size = valid_sizes[1]

            title_words = [
                w for w in words
                if round(w.get("size", 0), 1) == title_size
                and w.get("top", 0) < page_height * 0.45
            ]

            title_words.sort(key=lambda w: (round(w["top"]), w["x0"]))
            title_lines = _group_into_lines(title_words, tolerance=3)
            title = " ".join(" ".join(w["text"] for w in line) for line in title_lines)
            title = re.sub(r"-\s+", "", title)
            title = re.sub(r"\s+", " ", title).strip()

            if title_words:
                y_end_title = max(w["bottom"] for w in title_words)
            else:
                y_end_title = page_height * 0.15

            y_abstract = None
            for w in words:
                if w["text"].lower().startswith("abstract"):
                    y_abstract = w["top"]
                    break

            if y_abstract is None:
                y_abstract = page_height * 0.55

            middle_words = [
                w for w in words
                if w.get("top", 0) >= y_end_title - 2
                and w.get("top", 0) < y_abstract
            ]

            authors = _extract_authors_from_block(middle_words, page.width)

            return title, authors

    except Exception as e:
        print(f"  [ERROR] {pdf_path.name}: {e}")
        return None, None

def _group_into_lines(words: list, tolerance: float = 3) -> list:
    """Groups coordinate-based words into logical horizontal lines."""
    if not words:
        return []
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

def _detect_columns(line_words: list, page_width: float) -> list[list]:
    """Applies an adaptive threshold to group words into distinct visual columns."""
    if not line_words:
        return []
        
    line_words = sorted(line_words, key=lambda w: w["x0"])
    
    if len(line_words) == 1:
        return [line_words]

    gaps = []
    for i in range(len(line_words) - 1):
        gap = line_words[i+1]["x0"] - line_words[i]["x1"]
        gaps.append(max(0, gap))

    n = len(gaps)
    mean = sum(gaps) / n
    
    if n > 1:
        variance = sum((g - mean) ** 2 for g in gaps) / n
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0

    if std_dev > 2.0:
        threshold = max(8.0, mean + (1.5 * std_dev))
    else:
        threshold = page_width * 0.05

    columns = []
    current_column = [line_words[0]]

    for i, gap in enumerate(gaps):
        if gap > threshold:
            columns.append(current_column)
            current_column = [line_words[i+1]]
        else:
            current_column.append(line_words[i+1])

    if current_column:
        columns.append(current_column)

    return columns

def _extract_authors_from_block(words: list, page_width: float) -> str:
    """Identifies and extracts author names from the identified central word block."""
    if not words:
        return ""

    sorted_words = sorted(words, key=lambda w: (round(w["top"]), w["x0"]))
    lines = _group_into_lines(sorted_words, tolerance=4)

    text_lines = []
    for line in lines:
        text = " ".join(w["text"] for w in line).strip()
        if text:
            text_lines.append((text, line))

    authors = []
    i = 0
    while i < len(text_lines):
        text, line = text_lines[i]

        if len(text) < 3:
            i += 1
            continue

        if is_email_or_orcid(text):
            i += 1
            continue

        column_groups = _detect_columns(line, page_width)
        
        if len(column_groups) > 1:
            for group in column_groups:
                group_text = " ".join(w["text"] for w in group).strip()
                if is_email_or_orcid(group_text):
                    continue
                
                group_words = group_text.split()
                sub_names = []
                
                best_cut = -1
                smallest_diff = 999
                
                for j in range(2, len(group_words) - 1):
                    left_str = " ".join(group_words[:j])
                    right_str = " ".join(group_words[j:])
                    
                    starts_upper = group_words[j][0].isupper() or group_words[j][0] in "V´Í"
                    
                    if starts_upper and looks_like_name(left_str) and looks_like_name(right_str):
                        difference = abs(len(group_words[:j]) - len(group_words[j:]))
                        if difference < smallest_diff:
                            smallest_diff = difference
                            best_cut = j
                            
                if best_cut != -1:
                    sub_names.append(" ".join(group_words[:best_cut]))
                    sub_names.append(" ".join(group_words[best_cut:]))
                    
                    for sn in sub_names:
                        group_names = _extract_names_from_text_line(sn)
                        if group_names:
                            authors.extend(group_names)
                else:
                    group_names = _extract_names_from_text_line(group_text)
                    if group_names:
                        authors.extend(group_names)
            i += 1
            continue

        names = _extract_names_from_text_line(text)
        if names:
            authors.extend(names)
        elif _is_multiline_name_start(text):
            if i + 1 < len(text_lines):
                next_text, _ = text_lines[i + 1]
                combined = text + " " + next_text
                combined_names = _extract_names_from_text_line(combined)
                if combined_names:
                    authors.extend(combined_names)
                    i += 2
                    continue

        i += 1

    # Heuristic Reconnection: reassembles names fractured by prepositions or initials
    reconstructed_authors = []
    for a in authors:
        clean_a = a.strip().rstrip(",")
        if reconstructed_authors and (
            reconstructed_authors[-1].lower().endswith((" de", " da", " do", " das", " dos")) or 
            re.search(r'\b[A-Z]\.$', reconstructed_authors[-1])
        ):
            reconstructed_authors[-1] += " " + clean_a
        else:
            reconstructed_authors.append(clean_a)
    authors = reconstructed_authors

    seen = set()
    unique_authors = []
    for a in authors:
        norm_a = re.sub(r"\s+", " ", a).strip()
        key_a = norm_a.lower()
        if key_a not in seen and len(norm_a) > 3:
            seen.add(key_a)
            unique_authors.append(norm_a)

    return ", ".join(unique_authors)

def _is_multiline_name_start(text: str) -> bool:
    words = text.strip().split()
    if not words:
        return False
    first_word = words[0]
    return first_word[0].isupper() and 1 <= len(words) <= 3

def _extract_names_from_text_line(line: str) -> list:
    names = []

    initial_tokens = line.split()
    if len(initial_tokens) >= 3:
        if RE_ORDINAL_NUM.match(initial_tokens[0]) and RE_ORDINAL_SUF.match(initial_tokens[1]):
            line = " ".join(initial_tokens[2:])

    line = clean_superscripts(line)

    if RE_ORDINAL.match(line.split()[0] if line.split() else ""):
        parts = re.split(r"\d+(?:st|nd|rd|th)\s+", line, flags=re.IGNORECASE)
        for part in parts:
            part = part.strip()
            if part and looks_like_name(part):
                names.append(part)
        return names

    norm_line = re.sub(r"\s+and\s+", ", ", line, flags=re.IGNORECASE)
    comma_tokens = [t.strip() for t in norm_line.split(",") if t.strip()]

    if len(comma_tokens) >= 2:
        for token in comma_tokens:
            token = clean_superscripts(token).strip()
            if is_affiliation_line(token):
                continue
            if looks_like_name(token):
                names.append(token)
        if names:
            return names

    space_tokens = [t.strip() for t in re.split(r"\s{2,}", norm_line) if t.strip()]
    if len(space_tokens) >= 2:
        candidates = []
        for token in space_tokens:
            token = clean_superscripts(token).strip()
            if is_affiliation_line(token):
                continue
            if looks_like_name(token):
                candidates.append(token)
        if candidates:
            return candidates

    clean_line = clean_superscripts(line).strip()
    if not is_affiliation_line(clean_line) and looks_like_name(clean_line):
        names.append(clean_line)

    return names

# ---------------------------------------------------------------------------
# Strategy 2: Pure Text Fallback
# ---------------------------------------------------------------------------

def extract_by_pure_text(pdf_path: Path):
    """Fallback extraction method utilizing pure extract_text() layout."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if not pdf.pages:
                return None, None
            text = pdf.pages[0].extract_text(layout=False) or ""
    except Exception:
        return None, None

    if not text:
        return None, None

    lines = [l.strip() for l in text.split("\n") if l.strip()]

    abstract_idx = None
    for i, l in enumerate(lines):
        if l.lower().startswith("abstract"):
            abstract_idx = i
            break

    limit = abstract_idx if abstract_idx else min(len(lines), 30)
    authors_idx = _find_authors_start(lines, limit)

    if authors_idx is not None:
        title_lines = lines[:authors_idx]
    elif abstract_idx is not None:
        title_lines = lines[:abstract_idx]
    else:
        title_lines = lines[:4]

    title = " ".join(title_lines)
    title = re.sub(r"-\s+", "", title)
    title = re.sub(r"\s+", " ", title).strip()

    if authors_idx is None:
        return title, ""

    authors = []
    consecutive_affiliations = 0
    for line in lines[authors_idx:limit]:
        if not line:
            continue
        if line.lower().startswith("abstract"):
            break
        if is_email_or_orcid(line):
            continue

        names = _extract_names_from_text_line(line)
        if names:
            consecutive_affiliations = 0
            authors.extend(names)
        else:
            consecutive_affiliations += 1
            if consecutive_affiliations >= 6 and authors:
                break

    reconstructed_authors = []
    for a in authors:
        clean_a = a.strip().rstrip(",")
        if reconstructed_authors and (
            reconstructed_authors[-1].lower().endswith((" de", " da", " do", " das", " dos")) or 
            re.search(r'\b[A-Z]\.$', reconstructed_authors[-1])
        ):
            reconstructed_authors[-1] += " " + clean_a
        else:
            reconstructed_authors.append(clean_a)
    authors = reconstructed_authors

    seen = set()
    unique_authors = []
    for a in authors:
        key = a.strip().lower()
        if key not in seen and len(key) > 3:
            seen.add(key)
            unique_authors.append(a.strip())

    return title, ", ".join(unique_authors)

def _find_authors_start(lines: list, limit: int) -> int | None:
    for i, line in enumerate(lines[:limit]):
        if i < 1:  
            continue

        if RE_SUPERSCRIPT_INLINE.search(line):
            if not is_affiliation_line(line):
                return i

        leading_tokens = line.split()
        if leading_tokens and RE_ORDINAL.match(leading_tokens[0]):
            return i

        names = _extract_names_from_text_line(line)
        if len(names) >= 2:
            return i

        if i >= 2 and len(names) == 1:
            return i

    return None

# ---------------------------------------------------------------------------
# Core PDF Processing Pipeline
# ---------------------------------------------------------------------------

def process_pdf(pdf_path: Path) -> dict:
    title, authors = extract_by_font_and_position(pdf_path)

    title_ok = title and len(title) > 10 and not _title_has_mixed_authors(title)
    authors_ok = authors and len(authors) > 3

    if not title_ok or not authors_ok:
        title2, authors2 = extract_by_pure_text(pdf_path)

        if not title_ok and title2:
            title = title2
        if not authors_ok and authors2:
            authors = authors2

    if title:
        title = _clean_title(title)

    return {
        "file_id":      pdf_path.name,
        "pdf_title":    title or "[ERROR: title not extracted]",
        "pdf_authors":  authors or "[ERROR: authors not extracted]",
    }

def _title_has_mixed_authors(title: str) -> bool:
    if len(title) < 150:
        return False
    commas = title.count(",")
    if commas >= 3:
        names = _extract_names_from_text_line(title)
        if len(names) >= 2:
            return True
    return False

def _clean_title(title: str) -> str:
    title = re.sub(r"^\d+\s+", "", title)
    title = re.sub(r"-\s+", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    title = title.strip("*").strip()
    return title

# ---------------------------------------------------------------------------
# Batch Processing and Excel Generation
# ---------------------------------------------------------------------------

def process_directory(folder: Path, output_file: Path):
    pdfs = sorted(folder.rglob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in directory: {folder}")
        return

    print(f"Found {len(pdfs)} PDFs in '{folder}'")
    print(f"Generating output: {output_file}\n")

    results = []

    for pdf_path in pdfs:
        print(f"Processing: {pdf_path.name}")
        result = process_pdf(pdf_path)

        title = result["pdf_title"]
        authors = result["pdf_authors"]
        print(f"  Title  : {title[:90]}{'...' if len(title) > 90 else ''}")
        print(f"  Authors: {authors[:90]}{'...' if len(authors) > 90 else ''}")

        results.append(result)

    # Initialize Excel Workbook
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Extracted Articles"

    # Define standardized headers corresponding to SearchCopyright.xlsx
    ws.append(["FILE ID", "ARTICLE TITLE", "AUTHORS"])

    # Apply bold styling to header row
    for cell in ws[1]:
        cell.font = Font(bold=True)

    # Populate rows
    for res in results:
        ws.append([
            res["file_id"],       # FILE ID
            res["pdf_title"],     # ARTICLE TITLE
            res["pdf_authors"]    # AUTHORS
        ])

    # Save final artifact
    wb.save(output_file)
    print(f"\nExcel spreadsheet successfully generated with {len(results)} records: {output_file}")

# ---------------------------------------------------------------------------
# CLI Entry Point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Extracts titles and authors from scientific PDFs, generating a compliant XLSX file (v2.5)."
    )
    parser.add_argument(
        "--folder",
        default="02 - PDF Artigos Programacao",
        help="Target directory containing the PDF files.",
    )
    parser.add_argument(
        "--output",
        default="extracted_articles.xlsx",
        help="Target filename for the generated Excel spreadsheet.",
    )
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"Directory not found: {folder}")
        print("Please use the --folder argument to specify the correct path.")
        return

    process_directory(folder, Path(args.output))

if __name__ == "__main__":
    main()