# Imports
from PyPDF2 import PdfReader
from pathlib import Path

IEEE_STRING = [
    "979-8-3195-1715-9/26/$31.00©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 ©2026 IEEE",
    "979-8-3195-1715-9/26/$31,00 ©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 © 2026 IEEE",
]

def search_text(pdf_path):
    reader = PdfReader(pdf_path)

    for pagina in reader.pages:
        text = pagina.extract_text()
        if text:
            # verifica se qualquer padrão está presente
            if any(pattern in text for pattern in IEEE_STRING):
                return True

    return False
