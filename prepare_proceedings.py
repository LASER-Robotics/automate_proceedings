"""
Usage:
    python3 prepare_proceedings.py
"""

# Imports
import csv
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
from pathlib import Path
import argparse
import scripts.authors
import scripts.create_authors_index
import scripts.create_table_contents

# Configs
PATH_2 = "./pdfs_sorted/"
PATH_3 = "./numbered_papers/"
MUMB_CSV = "./sorted_pdfs.csv"

from reportlab.pdfbase.pdfmetrics import stringWidth

def create_overlay(num_pages, first_page):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    largura_pagina = 605 #tamanho da a4 + 10

    for i in range(first_page-1, first_page+num_pages-1):
        texto = f"{i+1}"
        font_size = 10

        can.setFont("Helvetica", font_size)

        largura_texto = stringWidth(texto, "Helvetica", font_size)

        x = (largura_pagina - largura_texto) / 2
        y = 10

        can.drawString(x, y, texto)
        can.showPage()

    can.save()
    packet.seek(0)
    return PdfReader(packet)


def numerar_pdf(input_path, output_path, num_pages, first_page):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    overlay = create_overlay(num_pages, first_page)

    for i in range(num_pages):
        page = reader.pages[i]
        page.merge_page(overlay.pages[i])
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)

def numerate(sorted_folder, sorted_pdfs, output):
    Path(output).mkdir(exist_ok=True)
    print("Processing papers")
    with open(sorted_pdfs, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            nome_pdf = row["proceedings_id"]
            num_paginas = int(row["#_pages"])
            pagina_inicial = int(row["#_first_page"])

            input_path = f"{sorted_folder}{nome_pdf}"
            output_path = f"{output}{nome_pdf}"
            try:
                # print(f"Processando: {nome_pdf} ({num_paginas} páginas)")
                numerar_pdf(input_path, output_path, num_paginas, pagina_inicial)
            except:
                print(f"Error processing file {nome_pdf}")

    print("Finalizado!")

if __name__ == "__main__":
    output_folder = "./reports/"
    parser = argparse.ArgumentParser(description="Numbering pages of the paper pdfs Tool")
    parser.add_argument("--sorted_folder", default="./pdfs_sorted", help="Path to the pdfs_sorted folder")
    parser.add_argument("--sorted_pdfs", default="sorted_pdfs.csv", help="Copyright log")
    parser.add_argument("--output", default="./numbered_papers", help="Path to output folder for the numbered pdfs")
    args = parser.parse_args()
    # numerate(args.sorted_folder + "/", output_folder + args.sorted_pdfs, args.output + "/")
    scripts.authors.main()
    scripts.create_authors_index.main()
    scripts.create_table_contents.main()




