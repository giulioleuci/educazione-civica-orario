import time
import pandas as pd
from datetime import datetime
from collections import defaultdict

from importlib.util import spec_from_loader, module_from_spec
from importlib.machinery import SourceFileLoader

spec = spec_from_loader("calendario", SourceFileLoader("calendario", "calendario-ed-civ-generator.py"))
calendario = module_from_spec(spec)
spec.loader.exec_module(calendario)

class MockCalendarioGenerator(calendario.CalendarioGenerator):
    def load_data(self):
        pass

    def initialize_variables(self):
        pass

    def __init__(self):
        config = calendario.CalendarioConfig(ore_tot_civics=30)
        super().__init__(config)
        self.classi_df = pd.DataFrame({'CLASSE': [f'Class_{i}' for i in range(100)]})

        self.slots_by_key = {}
        self.slot_disponibili = []
        for i, classe in enumerate(self.classi_df['CLASSE']):
            for d in range(100):  # 100 days
                for ora in range(1, 6): # 5 hours
                    key = f"{classe}_{d}_{ora}"
                    slot = {
                        'CLASSE': classe,
                        'DATA': datetime(2023, 1, 1),
                        'GIORNO': 'LUN',
                        'ORA': ora,
                        'DOCENTE_SOSTITUITO': 'Docente',
                        'KEY': key,
                        'SETTIMANA': d % 2
                    }
                    self.slot_disponibili.append(slot)
                    self.slots_by_key[key] = slot

        # Generate a valid individuo
        self.individuo = {}
        for classe in self.classi_df['CLASSE']:
            count = 0
            for d in range(100):
                for ora in range(1, 6):
                    if count >= self.ore_tot_civics:
                        break
                    key = f"{classe}_{d}_{ora}"
                    # Just setting something
                    self.individuo[key] = "Civics_1"
                    count += 1

        self.lista_classi = self.classi_df['CLASSE'].tolist()

    def verifica_vincoli_optimized(self, individuo):
        ore_per_classe = defaultdict(int)
        ore_settimanali_classe = defaultdict(lambda: defaultdict(int))

        for slot_key in individuo:
            slot_info = self.slots_by_key[slot_key]
            nome_classe = slot_info['CLASSE']
            data = slot_info['DATA']
            settimana = slot_info['SETTIMANA']
            ore_per_classe[nome_classe] += 1
            ore_settimanali_classe[nome_classe][settimana] += 1

            if ore_settimanali_classe[nome_classe][settimana] > 1:
                return False

        if not all(ore_per_classe[nome_classe] == self.ore_tot_civics
                   for nome_classe in self.lista_classi):
            return False

        return True

gen = MockCalendarioGenerator()

# Only measure the last part

import timeit
print("Original:")
print(timeit.timeit("all(ore_per_classe[nome_classe] == gen.ore_tot_civics for nome_classe in gen.classi_df['CLASSE'])", setup="ore_per_classe=defaultdict(int); gen.classi_df['CLASSE'];[ore_per_classe.update({c:30}) for c in gen.classi_df['CLASSE']]", globals=globals(), number=100000))

print("Optimized:")
print(timeit.timeit("all(ore_per_classe[nome_classe] == gen.ore_tot_civics for nome_classe in gen.lista_classi)", setup="ore_per_classe=defaultdict(int); gen.lista_classi;[ore_per_classe.update({c:30}) for c in gen.lista_classi]", globals=globals(), number=100000))
