# Imports
from PyPDF2 import PdfReader
from pathlib import Path
import csv

# Configs
PATH_2 = "./02 - PDF Artigos Programacao/"
IEEE_STRING = [
    "979-8-3195-1715-9/26/$31.00©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 ©2026 IEEE",
    "979-8-3195-1715-9/26/$31,00 ©2026 IEEE",
    "979-8-3195-1715-9/26/$31.00 © 2026 IEEE",
]


def count_page(pdf_path):
    reader = PdfReader(pdf_path)
    return len(reader.pages)


def search_text(pdf_path, text_list):
    reader = PdfReader(pdf_path)

    for pagina in reader.pages:
        text = pagina.extract_text()
        if text:
            # verifica se qualquer padrão está presente
            if any(pattern in text for pattern in text_list):
                return True

    return False


def count_pages():
    folder = Path(PATH_2)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    files = sorted(files)

    with open("resultado.csv", mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["id", "pdf", "paginas", "string_encontrada"])

        for idx, f in enumerate(files, start=1):
            caminho = f"{PATH_2}{f}"

            pages = count_page(caminho)
            text_found = search_text(caminho, IEEE_STRING)

            writer.writerow([idx, f, pages, text_found])

            print(f"[{idx}] {f} -> {pages} páginas | string: {text_found}")


if __name__ == "__main__":
    count_pages()