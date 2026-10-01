import itertools
import sys
from datetime import datetime, timedelta
from collections import defaultdict

import pytest
from conftest import real_modules
import generator_mod
from generator_mod import CalendarioGenerator


@pytest.fixture(autouse=True)
def numpy_pandas_reali(monkeypatch):
    # conftest sostituisce numpy/pandas con mock, ma ortools ha bisogno di quelli reali
    for nome, modulo in real_modules.items():
        monkeypatch.setitem(sys.modules, nome, modulo)


class Gen(CalendarioGenerator):
    def __init__(self, classi, docenti_classi, ore_tot, slot_per_classe):
        # slot_per_classe: {classe: [(settimana, ora, docente_sostituito), ...]}
        self.classi_list = classi
        self.docenti_civics_classi = docenti_classi
        self.ore_tot_civics = ore_tot
        self.allow_teacher_replace_self = True
        self.num_cores = 1
        self.tempo_max_secondi = 20
        self.giorni_settimana = ['LUN']
        self.docenti_civics_organico = defaultdict(set)
        self.disponibilita_civics = {d: {'LUN': [True, True]} for d in docenti_classi}
        base = datetime(2026, 10, 5)  # lunedì
        self.slot_disponibili = [
            {'CLASSE': c, 'DATA': base + timedelta(weeks=w), 'GIORNO': 'LUN', 'ORA': ora,
             'DOCENTE_SOSTITUITO': doc, 'KEY': f"{c}_{w}_{ora}", 'SETTIMANA': w}
            for c, slots in slot_per_classe.items() for w, ora, doc in slots]
        self._precalcola_lookups()


def _brute_force(gen, docente):
    # Ottimo esaustivo per un solo docente civics: tutte le scelte valide, fitness con calcola_fitness
    per_classe = []
    for c in gen.classi_list:
        scelte = [s for s in itertools.combinations(gen.slots_by_class[c], gen.ore_tot_civics)
                  if len({x['SETTIMANA'] for x in s}) == len(s)]
        per_classe.append(scelte)
    migliore = float('inf')
    for combo in itertools.product(*per_classe):
        slots = [s for scelta in combo for s in scelta]
        if len({(s['DATA'], s['ORA']) for s in slots}) != len(slots):
            continue
        migliore = min(migliore, gen.calcola_fitness({s['KEY']: docente for s in slots}))
    return migliore


def test_soluzione_ottima_e_valida():
    slot = {c: [(1, 1, 'X'), (2, 1, 'Y'), (3, 1, 'X'), (3, 2, 'Z'), (4, 1, 'Y')] for c in ('A', 'B')}
    gen = Gen(['A', 'B'], {'C': ['A', 'B']}, 2, slot)
    individuo = gen.risolvi()
    assert gen.verifica_vincoli(individuo)
    assert gen.calcola_fitness(individuo) == pytest.approx(_brute_force(gen, 'C'), abs=0.05)


def test_componenti_una_per_docente():
    slot = {c: [(1, 1, 'X'), (2, 1, 'Y')] for c in ('A', 'B', 'C')}
    gen = Gen(['A', 'B', 'C'], {'D1': ['A', 'B'], 'D2': ['C']}, 1, slot)
    assert sorted(map(sorted, gen._componenti())) == [['A', 'B'], ['C']]


def test_infeasible_esce():
    gen = Gen(['A'], {'C': ['A']}, 3, {'A': [(1, 1, 'X'), (2, 1, 'Y')]})
    with pytest.raises(SystemExit):
        gen.risolvi()


def test_tempo_risparmiato_passa_ai_modelli_successivi(monkeypatch):
    gen = Gen(['A', 'B', 'C'], {'D1': ['A'], 'D2': ['B'], 'D3': ['C']}, 1, {c: [(1, 1, 'X')] for c in 'ABC'})
    gen.tempo_max_secondi = 100
    orologio = [0]
    monkeypatch.setattr(generator_mod.time, 'monotonic', lambda: orologio[0])
    limiti = []

    def finto(classi, tempo):
        limiti.append(tempo)
        orologio[0] += 10 if classi == ['A'] else tempo  # il primo modello dimostra l'ottimo subito
        return {}

    gen._risolvi_componente = finto
    gen.risolvi()
    assert limiti == [100, 145, 145]
