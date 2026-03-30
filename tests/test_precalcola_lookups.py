import pytest
from collections import defaultdict
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self, slot_disponibili, docenti_civics_classi, classi_list, ore_tot_civics):
        # Bypass original __init__ to avoid file loading and initialization logic
        self.slot_disponibili = slot_disponibili
        self.docenti_civics_classi = docenti_civics_classi
        self.classi_list = classi_list
        self.ore_tot_civics = ore_tot_civics

def test_precalcola_lookups_basic():
    slot_disponibili = [
        {'CLASSE': '1A', 'KEY': '1A_K1', 'DOCENTE_SOSTITUITO': 'Doc1'},
        {'CLASSE': '1A', 'KEY': '1A_K2', 'DOCENTE_SOSTITUITO': 'Doc1'},
        {'CLASSE': '2B', 'KEY': '2B_K1', 'DOCENTE_SOSTITUITO': 'Doc2'},
    ]
    docenti_civics_classi = {
        'CivicDoc1': ['1A', '2B'],
        'CivicDoc2': ['1A'],
    }
    classi_list = ['1A', '2B']
    ore_tot_civics = 30

    gen = MockGenerator(slot_disponibili, docenti_civics_classi, classi_list, ore_tot_civics)
    gen._precalcola_lookups()

    # Check slots_by_class
    assert len(gen.slots_by_class['1A']) == 2
    assert len(gen.slots_by_class['2B']) == 1
    assert gen.slots_by_class['1A'][0]['KEY'] == '1A_K1'

    # Check slots_by_key
    assert '1A_K1' in gen.slots_by_key
    assert gen.slots_by_key['1A_K1'] == slot_disponibili[0]

    # Check ore_totali_docente_per_classe
    assert gen.ore_totali_docente_per_classe['1A']['Doc1'] == 2
    assert gen.ore_totali_docente_per_classe['2B']['Doc2'] == 1

    # Check docenti_per_classe
    assert set(gen.docenti_per_classe['1A']) == {'CivicDoc1', 'CivicDoc2'}
    assert set(gen.docenti_per_classe['2B']) == {'CivicDoc1'}

    # Check P_per_classe
    # For 1A: total teaching hours = 2. P = (30 / 2) * 100 = 1500.0
    # For 2B: total teaching hours = 1. P = (30 / 1) * 100 = 3000.0
    assert gen.P_per_classe['1A'] == 1500.0
    assert gen.P_per_classe['2B'] == 3000.0

def test_precalcola_lookups_empty_inputs():
    gen = MockGenerator([], {}, [], 30)
    gen._precalcola_lookups()

    assert len(gen.slots_by_class) == 0
    assert len(gen.slots_by_key) == 0
    assert len(gen.ore_totali_docente_per_classe) == 0
    assert len(gen.docenti_per_classe) == 0
    assert len(gen.P_per_classe) == 0

def test_precalcola_lookups_zero_teaching_hours():
    # Test division by zero handling in P_per_classe calculation
    # Even if class is in classi_list, it has 0 teaching hours if it has no slots
    slot_disponibili = []
    docenti_civics_classi = {}
    classi_list = ['1A']
    ore_tot_civics = 30

    gen = MockGenerator(slot_disponibili, docenti_civics_classi, classi_list, ore_tot_civics)
    gen._precalcola_lookups()

    # For 1A: total teaching hours = 0. P = 0
    assert '1A' in gen.P_per_classe
    assert gen.P_per_classe['1A'] == 0

def test_precalcola_lookups_partial_hours():
    # Test a mix of classes with and without teaching hours
    slot_disponibili = [
        {'CLASSE': '1A', 'KEY': '1A_K1', 'DOCENTE_SOSTITUITO': 'Doc1'},
    ]
    docenti_civics_classi = {}
    classi_list = ['1A', '2B']
    ore_tot_civics = 30

    gen = MockGenerator(slot_disponibili, docenti_civics_classi, classi_list, ore_tot_civics)
    gen._precalcola_lookups()

    assert gen.P_per_classe['1A'] == 3000.0
    assert gen.P_per_classe['2B'] == 0
