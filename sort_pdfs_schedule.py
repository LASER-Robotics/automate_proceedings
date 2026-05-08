# Imports
import argparse
import pandas as pd
import shutil as stl
from pathlib import Path
from camera_ready_check import processar_sorted
import csv

def copy_article(PATH, SCHEDULE, COPYRIGHT):
    
    db = pd.read_excel(SCHEDULE)
    db = db.values.tolist()

    OUTPUT = "./pdfs_sorted/"

    Path(OUTPUT).mkdir(exist_ok=True)

    folder = Path(PATH)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    
    print(f"Renaming pdfs...")
    for count in range(1, len(db)+1):
        name = f"{count:03d}.pdf"
        
        id_original = int(db[count-1][0])
        origem_name = f"{id_original:03d}.pdf"
        
        origem_completa = f"{PATH}{origem_name}"
        destino_completo = f"{OUTPUT}{name}"

        try:
            stl.copy2(origem_completa, destino_completo)
        except Exception as e:
            print(f"{e}")

    print(f"Processing papers...")
    processar_sorted(PATH, SCHEDULE, COPYRIGHT)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Copyright Compliance Validation Tool")
    parser.add_argument("--schedule", default="artigos_programacao.xlsx", help="Path to extracted PDF data")
    parser.add_argument("--path", default="./01 - PDF Artigos CMT", help="Path to official copyright DB")
    parser.add_argument("--copyright", default="./SearchCopyright.xlsx", help="Copyright log")
    args = parser.parse_args()
    copy_article(args.path + "/", args.schedule, args.copyright)
