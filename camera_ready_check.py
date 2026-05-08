"""
Input: Path to a folder with all the pdfs named named with 3 digit number ex: 007.pdf, 092.pdf, etc

Usage:
    python3 camera_ready_check.py --path camera_ready_folder_path
"""

# Imports
import argparse
from PyPDF2 import PdfReader
from pathlib import Path
import pandas as pd
import csv
from pdfexpress_compliance_check import check_pdf_creator
from pdf_metadata_extractor import process_pdf
from scripts.contagem_de_paginas import count_page
from scripts.ieee_string_copyright import search_text
from ecf_compliance_check import run_pipeline
from ecf_compliance_check import signed_copyright

count = 1

# TODO: verificar se o autor assinou o copyrigt form
def processar(PATH, schedule):
    global count
    folder = Path(PATH + "/")
    files = [f.name for f in folder.iterdir() if f.is_file()]
    files = sorted(files)

    csv_name = "camera_ready_report.csv"
    print("Processing papers...")
    with open(csv_name, mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["cmt_id", "title_pdf", "authors_pdf", "#_pages", "copyright_notice", "ecf_status", "ieee_compliace"])

        for f in files:
            caminho = f"{PATH}{f}"
            folder_obj = Path(caminho)
            extrator = process_pdf(folder_obj)

            pages = count_page(caminho)
            text_found = search_text(caminho)
            ieee_complance_check = check_pdf_creator(caminho)

            pagina_inicial = count
            count += pages
            pagina_final = count - 1

            copyright_confirmation = signed_copyright(extrator["pdf_title"], schedule)

            writer.writerow([f, extrator["pdf_title"], extrator["pdf_authors"], pages, text_found, copyright_confirmation, ieee_complance_check])
            
    print(f"Done. See {csv_name}")

def processar_sorted(PATH, schedule, COPYRIGHT):
    db = pd.read_excel(schedule)
    db = db.values.tolist()
    global count

    folder = Path(PATH)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    files = sorted(files)

    csv_name = "sorted_pdfs.csv"

    with open(csv_name, mode="w", newline="", encoding="utf-8") as f_csv:
        writer = csv.writer(f_csv)
        writer.writerow(["proceedings_id", "cmt_id", "title_pdf", "authors_pdf", "#_pages", "#_first_page", "#_last_page"])

        for idx, f in enumerate(db, start=1):
            name = f"{f[0]:03d}.pdf"

            caminho = f"{PATH}{name}"
            folder_obj = Path(caminho)
            extrator = process_pdf(folder_obj)

            pages = count_page(caminho)
            text_found = search_text(caminho)
            ieee_complance_check = check_pdf_creator(caminho)

            pagina_inicial = count
            count += pages
            pagina_final = count - 1

            writer.writerow([f"{idx:03d}.pdf", name, extrator["pdf_title"], extrator["pdf_authors"], pages, pagina_inicial, pagina_final])

    output_file_name = "final_compliance_report.csv"
    run_pipeline(csv_name, COPYRIGHT, output_file_name)
            
    print(f"Done. See {csv_name}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Camera-Ready Verification Tool")
    parser.add_argument("--path", default="./01 - PDF Artigos CMT", help="Path to the folder with the Camera-Ready Files Named 001.pdf, 002.pdf, etc")
    parser.add_argument("--copyright", default="./SearchCopyright.xlsx", help="Path to the file")
    parser.add_argument("--schedule", default="./artigos_programacao.xlsx", help="Path to the folder with the Camera-Ready Files Named 001.pdf, 002.pdf, etc")
    args = parser.parse_args()
    processar(args.path + "/", args.copyright)