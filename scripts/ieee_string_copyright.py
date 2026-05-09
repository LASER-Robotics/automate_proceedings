# Imports
from PyPDF2 import PdfReader
from pathlib import Path

# COPYRIGHT NOTICE OF CROS 2026
IEEE_STRING = [
    "979-8-3195-1715-9/26/$31.00©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 ©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 © 2026 IEEE"
]

# TODO: force authors to use the correct format as described in the LOA -> 979-8-3195-1715-9/26/$31.00 ©2026 IEEE
def search_text(pdf_path):
    reader = PdfReader(pdf_path)

    text = reader.pages[0].extract_text()
    if text:
        # check if any of the IEEE_STRING is on the first page
        if any(pattern in text for pattern in IEEE_STRING):
            return True

    return False