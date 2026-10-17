import pytest
from generator_mod import CalendarioGenerator
import pandas as pd

class MockGenerator(CalendarioGenerator):
    def __init__(self, docenti_civics_df):
        self.docenti_civics_df = docenti_civics_df

def test_parse_assegnazioni_docenti_basic():
    # Setup
    data = [
        {'DOCENTE': 'DocenteA', 'CLASSI': '1A;2B;3C'},
        {'DOCENTE': 'DocenteB', 'CLASSI': '4D;5E'}
    ]
    df = pd.DataFrame(data)
    gen = MockGenerator(df)

    # Run
    gen._parse_assegnazioni_docenti()

    # Verify
    assert 'DocenteA' in gen.docenti_civics_classi
    assert gen.docenti_civics_classi['DocenteA'] == ['1A', '2B', '3C']
    assert 'DocenteB' in gen.docenti_civics_classi
    assert gen.docenti_civics_classi['DocenteB'] == ['4D', '5E']

def test_parse_assegnazioni_docenti_empty():
    # Setup
    data = []
    df = pd.DataFrame(data)
    gen = MockGenerator(df)

    # Run
    gen._parse_assegnazioni_docenti()

    # Verify
    assert gen.docenti_civics_classi == {}

def test_parse_assegnazioni_docenti_single_class():
    # Setup
    data = [
        {'DOCENTE': 'DocenteC', 'CLASSI': '1A'}
    ]
    df = pd.DataFrame(data)
    gen = MockGenerator(df)

    # Run
    gen._parse_assegnazioni_docenti()

    # Verify
    assert 'DocenteC' in gen.docenti_civics_classi
    assert gen.docenti_civics_classi['DocenteC'] == ['1A']
