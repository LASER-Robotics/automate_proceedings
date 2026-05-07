# Imports
from PyPDF2 import PdfReader
from pathlib import Path
import pandas as pd
import csv
from compliance_check import check_pdf_creator
from pdf_metadata_extractor import process_pdf
from scripts.contagem_de_paginas import count_page
from scripts.ieee_string_copyright import search_text

# Configs
# Folder with all the pdfs named by ID (001.pdf, 002.pdf, etc)
PATH_1 = "./01 - PDF Artigos CMT/"

count = 1

def processar():
    global count
    folder = Path(PATH_1)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    files = sorted(files)

    with open("dados_dos_artigos.csv", mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["cmt_id", "title_pdf", "authors_pdf", "#_pages", "copyright", "ieee_compliace", "#_first_page", "#_last_page"])

        for f in files:                        
            caminho = f"{PATH_1}{f}"
            folder_obj = Path(caminho)
            extrator = process_pdf(folder_obj)

            pages = count_page(caminho)
            text_found = search_text(caminho)
            ieee_complance_check = check_pdf_creator(caminho)

            pagina_inicial = count
            count += pages
            pagina_final = count - 1

            writer.writerow([f, extrator["pdf_title"], extrator["pdf_authors"], pages, text_found, ieee_complance_check, pagina_inicial, pagina_final])
            
    print(f"csv dados_dos_artigos.csv criado com sucesso!")


if __name__ == "__main__":
    processar()