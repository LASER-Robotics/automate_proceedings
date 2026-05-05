# Imports
import pandas as pd
import shutil as stl
from pathlib import Path

# Configs
DATABASE = "./artigos_programacao.xlsx"
PATH_1 = "./01 - PDF Artigos CMT/"
PATH_2 = "./02 - PDF Artigos Programacao/"

def copy_article():
    
    db = pd.read_excel(DATABASE)
    db = db.values.tolist()

    folder = Path(PATH_1)
    files = [f.name for f in folder.iterdir() if f.is_file()]
    
    for count in range(1, len(db)+1):
        name = f"{count:03d}.pdf"
        
        id_original = int(db[count-1][0])
        origem_name = f"{id_original:03d}.pdf"
        
        origem_completa = f"{PATH_1}{origem_name}"
        destino_completo = f"{PATH_2}{name}"

        try:
            stl.copy2(origem_completa, destino_completo)
            print(f"Copiado: {origem_name} -> {name}")
        except Exception as e:
            print(f"{e}")


if __name__ == "__main__":
    copy_article()
