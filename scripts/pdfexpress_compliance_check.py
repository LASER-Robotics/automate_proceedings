#!/usr/bin/env python3

import csv
import sys
from pathlib import Path

from pypdf import PdfReader


TARGET_TEXT = "Certified by IEEE PDFExpress"
OUTPUT_NAME = "compliance_check.csv"


def check_pdf_creator(pdf_path: Path) -> str:
    try:
        reader = PdfReader(str(pdf_path))

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                return ""

        metadata = reader.metadata
        if not metadata:
            return ""

        creator = metadata.get("/Creator") or metadata.get("creator") or ""
        if TARGET_TEXT in creator:
            return "IEEE Express Compliant"

        return ""

    except Exception:
        return ""


def main():
    if len(sys.argv) != 2:
        print(f"Uso: {Path(sys.argv[0]).name} <path_to_pdfs_directory>")
        sys.exit(1)

    input_dir = Path(sys.argv[1])

    if not input_dir.is_dir():
        print(f"Error: '{input_dir}' invalid directory.")
        sys.exit(1)

    pdf_files = sorted(input_dir.glob("*.pdf"))

    if not pdf_files:
        print("No PDF found in the directory.")
        sys.exit(0)

    output_csv = input_dir / OUTPUT_NAME

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["pdf_name", "status"])

        for pdf in pdf_files:
            status = check_pdf_creator(pdf)
            writer.writerow([pdf.name, status])

    print(f"CSV sucessfully generated in: {output_csv}")


if __name__ == "__main__":
    main()
