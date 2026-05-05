# Imports
import csv
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from io import BytesIO
from pathlib import Path


# Configs
PATH_2 = "./02 - PDF Artigos Programacao/"
PATH_3 = "./05 - PDF Artigos Programacao enumerados/"
MUMB_CSV = "./resultado.csv"

from reportlab.pdfbase.pdfmetrics import stringWidth

def create_overlay(num_pages):
    packet = BytesIO()
    can = canvas.Canvas(packet)

    largura_pagina = 605 #tamanho da a4 + 10

    for i in range(num_pages):
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


def numerar_pdf(input_path, output_path, num_pages):
    reader = PdfReader(input_path)
    writer = PdfWriter()

    overlay = create_overlay(num_pages)

    for i in range(num_pages):
        page = reader.pages[i]
        page.merge_page(overlay.pages[i])
        writer.add_page(page)

    with open(output_path, "wb") as f:
        writer.write(f)


def numerate():
    with open(MUMB_CSV, newline='', encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:
            nome_pdf = row["pdf"]
            num_paginas = int(row["paginas"])

            input_path = f"{PATH_2}{nome_pdf}"
            output_path = f"{PATH_3}{nome_pdf}"
            try:
                print(f"Processando: {nome_pdf} ({num_paginas} páginas)")
                numerar_pdf(input_path, output_path, num_paginas)
            except:
                print(f"Erro ao processar pdf {nome_pdf}")

    print("Finalizado!")


if __name__ == "__main__":
    numerate()




