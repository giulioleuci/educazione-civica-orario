import time
import pandas as pd
from datetime import datetime
import os
import shutil

# Setup minimal dummy env
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

spec = spec_from_loader("calendario", SourceFileLoader("calendario", "calendario-ed-civ-generator.py"))
calendario = module_from_spec(spec)
spec.loader.exec_module(calendario)

def run_benchmark():
    os.makedirs("test_output", exist_ok=True)
    # Mock data
    num_docenti = 200
    docenti_civics_df = pd.DataFrame({'DOCENTE': [f'Docente_{i}' for i in range(num_docenti)]})

    calendario_entries = []
    # Add entries for docenti
    for d in range(num_docenti):
        for w in range(10): # 10 weeks
            calendario_entries.append({
                'DATA': datetime(2024, 1, 1),
                'GIORNO': 'LUN',
                'ORA': 1,
                'CLASSE': f'Classe_0',
                'DOCENTE_CIVICS': f'Docente_{d}',
                'DOCENTE_SOSTITUITO': 'Sostituito_0'
            })

    # Add a lot of irrelevant entries to make the N*M worse
    for _ in range(20000):
        calendario_entries.append({
            'DATA': datetime(2024, 1, 1),
            'GIORNO': 'LUN',
            'ORA': 1,
            'CLASSE': f'Classe_0',
            'DOCENTE_CIVICS': f'Other_Docente',
            'DOCENTE_SOSTITUITO': 'Sostituito_0'
        })

    start = time.time()
    calendario.genera_orario_docenti(calendario_entries, docenti_civics_df, "test_output")
    end = time.time()
    print(f"Time taken for genera_orario_docenti: {end - start:.4f} seconds")
    shutil.rmtree("test_output")

if __name__ == '__main__':
    run_benchmark()
