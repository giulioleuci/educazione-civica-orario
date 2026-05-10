import pytest
from collections import defaultdict
from generator_mod import CalendarioGenerator
import pandas as pd

class MockGenerator(CalendarioGenerator):
    def __init__(self, classi_df, docenti_civics_classi, giorni_settimana):
        self.classi_df = classi_df
        self.docenti_civics_classi = docenti_civics_classi
        self.giorni_settimana = giorni_settimana

def test_identifica_docenti_civics_organico_basic():
    # Setup
    classi_data = [
        {'CLASSE': '1A', 'DOC LUN': 'Docente1;Docente2', 'DOC MAR': 'Docente3'},
        {'CLASSE': '2B', 'DOC LUN': 'Docente4', 'DOC MAR': 'Docente1;Docente5'}
    ]
    classi_df = pd.DataFrame(classi_data)
    docenti_civics_classi = {'Docente1': ['1A', '2B'], 'Docente3': ['1A'], 'Docente5': ['2B']}
    giorni_settimana = ['LUN', 'MAR']

    gen = MockGenerator(classi_df, docenti_civics_classi, giorni_settimana)

    # Run
    gen._identifica_docenti_civics_organico()

    # Verify
    assert '1A' in gen.docenti_civics_organico
    assert set(gen.docenti_civics_organico['1A']) == {'Docente1', 'Docente3'}
    assert '2B' in gen.docenti_civics_organico
    assert set(gen.docenti_civics_organico['2B']) == {'Docente1', 'Docente5'}

def test_identifica_docenti_civics_organico_no_match():
    # Setup
    classi_data = [
        {'CLASSE': '1A', 'DOC LUN': 'Docente2', 'DOC MAR': 'Docente4'}
    ]
    classi_df = pd.DataFrame(classi_data)
    docenti_civics_classi = {'Docente1': ['1A', '2B'], 'Docente3': ['1A']}
    giorni_settimana = ['LUN', 'MAR']

    gen = MockGenerator(classi_df, docenti_civics_classi, giorni_settimana)

    # Run
    gen._identifica_docenti_civics_organico()

    # Verify
    # Organico should have an empty set for 1A
    assert len(gen.docenti_civics_organico['1A']) == 0
