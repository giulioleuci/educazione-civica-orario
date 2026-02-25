
import pytest
from generator_mod import CalendarioGenerator

from collections import defaultdict

class MockGenerator(CalendarioGenerator):
    def __init__(self, classi_df, slot_disponibili):
        # Bypass the original __init__ to avoid file loading and initialization logic
        self.classi_df = classi_df
        self.slot_disponibili = slot_disponibili
        self.slots_by_class = defaultdict(list)
        for slot in self.slot_disponibili:
            self.slots_by_class[slot['CLASSE']].append(slot)

def test_calcola_statistiche_basic():
    # Setup
    classi_df = {'CLASSE': ['1A']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K1'},
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K2'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # Input: Docente1 lost 1 hour out of 2
    calendario = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1'},
    ]

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    assert len(stats) == 1
    assert stats[0]['CLASSE'] == '1A'
    assert stats[0]['DOCENTE'] == 'Docente1'
    assert stats[0]['ORE_PERSE'] == 1
    assert stats[0]['ORE_TOTALI'] == 2
    assert stats[0]['PERCENTUALE_ORE_PERSE'] == '50.00'

def test_calcola_statistiche_empty_calendar():
    # Setup
    classi_df = {'CLASSE': ['1A']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K1'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # Input: Empty calendar (no hours lost)
    calendario = []

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    assert len(stats) == 1
    assert stats[0]['ORE_PERSE'] == 0
    assert stats[0]['ORE_TOTALI'] == 1
    assert stats[0]['PERCENTUALE_ORE_PERSE'] == '0.00'

def test_calcola_statistiche_all_hours_lost():
    # Setup
    classi_df = {'CLASSE': ['1A']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K1'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # Input: All available hours lost
    calendario = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1'},
    ]

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    assert len(stats) == 1
    assert stats[0]['ORE_PERSE'] == 1
    assert stats[0]['ORE_TOTALI'] == 1
    assert stats[0]['PERCENTUALE_ORE_PERSE'] == '100.00'

def test_calcola_statistiche_multiple_classes_and_teachers():
    # Setup
    classi_df = {'CLASSE': ['1A', '2B']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'T1', 'KEY': '1A_1'},
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'T1', 'KEY': '1A_2'},
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'T2', 'KEY': '1A_3'},
        {'CLASSE': '2B', 'DOCENTE_SOSTITUITO': 'T3', 'KEY': '2B_1'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # Input
    calendario = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'T1'}, # 1/2 for T1 in 1A
        {'CLASSE': '2B', 'DOCENTE_SOSTITUITO': 'T3'}, # 1/1 for T3 in 2B
    ]

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    # T1 and T2 are in 1A, T3 is in 2B.
    # For 1A: ore_totali_docente = {'T1': 2, 'T2': 1}
    # For 2B: ore_totali_docente = {'T3': 1}
    # Total 3 entries in stats.
    # It iterates over classes:
    # 1A -> T1, T2 -> 2 entries
    # 2B -> T3 -> 1 entry
    # Total 3 entries. Correct.
    assert len(stats) == 3

    stat_1A_T1 = next(s for s in stats if s['CLASSE'] == '1A' and s['DOCENTE'] == 'T1')
    assert stat_1A_T1['ORE_PERSE'] == 1
    assert stat_1A_T1['PERCENTUALE_ORE_PERSE'] == '50.00'

    stat_1A_T2 = next(s for s in stats if s['CLASSE'] == '1A' and s['DOCENTE'] == 'T2')
    assert stat_1A_T2['ORE_PERSE'] == 0
    assert stat_1A_T2['PERCENTUALE_ORE_PERSE'] == '0.00'

    stat_2B_T3 = next(s for s in stats if s['CLASSE'] == '2B' and s['DOCENTE'] == 'T3')
    assert stat_2B_T3['ORE_PERSE'] == 1
    assert stat_2B_T3['PERCENTUALE_ORE_PERSE'] == '100.00'

def test_calcola_statistiche_rounding():
    # Setup
    classi_df = {'CLASSE': ['1A']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K1'},
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K2'},
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K3'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # Input: 1 hour lost out of 3 = 33.3333...%
    calendario = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1'},
    ]

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    assert stats[0]['PERCENTUALE_ORE_PERSE'] == '33.33'

def test_calcola_statistiche_no_slots_for_class():
    # Setup
    classi_df = {'CLASSE': ['1A', '2B']}
    slot_disponibili = [
        {'CLASSE': '1A', 'DOCENTE_SOSTITUITO': 'Docente1', 'KEY': 'K1'},
    ]
    gen = MockGenerator(classi_df, slot_disponibili)

    # 2B has no slots in slot_disponibili
    calendario = []

    # Run
    stats = gen.calcola_statistiche(calendario)

    # Verify
    # Only Docente1 in 1A should be present
    assert len(stats) == 1
    assert stats[0]['CLASSE'] == '1A'
