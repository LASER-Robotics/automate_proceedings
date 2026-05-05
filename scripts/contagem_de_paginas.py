# Imports
from PyPDF2 import PdfReader
from pathlib import Path

def count_page(pdf_path):
    reader = PdfReader(pdf_path)
    return len(reader.pages)

