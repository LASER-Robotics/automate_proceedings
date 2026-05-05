# Imports
from PyPDF2 import PdfReader
from pathlib import Path
import pandas as pd
import csv
from compliance_check import check_pdf_creator
from scripts.contagem_de_paginas import count_page
from scripts.ieee_string_copyright import search_text

# Configs
PATH_1 = "./01 - PDF Artigos CMT/"
DATABASE = "./artigos_programacao.xlsx"


# global var
count = 1


def processar():
    db = pd.read_excel(DATABASE)
    db = db.values.tolist()
    global count
    
    folder = Path(PATH_1)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    files = sorted(files)

    with open("dados_dos_artigos.csv", mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["id", "pdf", "titulo_artigo", "paginas", "pagina_inicial", "pagina_final", "string_encontrada", "ieee_complace"])

        for idx, f in enumerate(db, start=1):
            name = f"{f[0]:03d}.pdf"
            
            caminho = f"{PATH_1}{name}"

            pages = count_page(caminho)
            text_found = search_text(caminho)
            ieee_complance_check = check_pdf_creator(caminho)


            titulo = f[1]
            pagina_inicial = count
            count += pages
            pagina_final = count - 1

            writer.writerow([idx, name, titulo, pages, pagina_inicial, pagina_final, text_found, ieee_complance_check])
    print(f"csv dados_dos_artigos.csv criado com sucesso!")


if __name__ == "__main__":
    processar()