import time
import pandas as pd
from datetime import datetime
from collections import defaultdict

# Setup minimal dummy env
from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

spec = spec_from_loader("calendario", SourceFileLoader("calendario", "calendario-ed-civ-generator.py"))
calendario = module_from_spec(spec)
spec.loader.exec_module(calendario)

# Mock some data for the benchmark
class MockCalendarioGenerator(calendario.CalendarioGenerator):
    def load_data(self):
        pass

    def initialize_variables(self):
        pass

    def __init__(self):
        config = calendario.CalendarioConfig(ore_tot_civics=30)
        super().__init__(config)
        self.docenti_civics_organico = defaultdict(set)
        self.classi_df = pd.DataFrame({'CLASSE': [f'Class_{i}' for i in range(50)]})
        self.classi_list = self.classi_df['CLASSE'].tolist()

        for classe in self.classi_list:
            for i in range(200):
                self.docenti_civics_organico[classe].add(f'Other_Docente_{i}')
            self.docenti_civics_organico[classe].add('Docente_0')

        self.slots_by_class = defaultdict(list)
        self.slots_by_key = {}
        self.ore_totali_docente_per_classe = defaultdict(lambda: defaultdict(int))

        self.slot_disponibili = []
        for i, classe in enumerate(self.classi_df['CLASSE']):
            for d in range(200):  # 200 days
                for ora in range(1, 6): # 5 hours
                    docente = f'Docente_{d % 10}'
                    key = f"{classe}_{d}_{ora}"
                    slot = {
                        'CLASSE': classe,
                        'DATA': datetime(2023, 1, 1), # mock
                        'GIORNO': 'LUN',
                        'ORA': ora,
                        'DOCENTE_SOSTITUITO': docente,
                        'KEY': key,
                        'SETTIMANA': 1
                    }
                    self.slot_disponibili.append(slot)
                    self.slots_by_class[classe].append(slot)
                    self.slots_by_key[key] = slot
                    self.ore_totali_docente_per_classe[classe][docente] += 1

        self.individuo = {}
        for key in self.slots_by_key:
            if hash(key) % 10 == 0: # 10% of slots have civics
                self.individuo[key] = f'Civics_{hash(key) % 3}'

gen = MockCalendarioGenerator()

start = time.time()
for _ in range(100):
    gen.calcola_fitness(gen.individuo)
end = time.time()
print(f"Time taken for 100 fitness evaluations: {end - start:.4f} seconds")
