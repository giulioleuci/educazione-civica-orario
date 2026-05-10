import pytest
import pandas as pd
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self):
        pass

def test_parse_orari_classi_success():
    gen = MockGenerator()
    gen.giorni_settimana = ['LUNEDÌ', 'MARTEDÌ']

    data = [
        {'CLASSE': '1A', 'DOC LUNEDÌ': 'Rossi;Bianchi', 'DOC MARTEDÌ': 'Verdi'},
        {'CLASSE': '2B', 'DOC LUNEDÌ': 'Neri', 'DOC MARTEDÌ': 'Gialli;Blu'}
    ]
    gen.classi_df = pd.DataFrame(data=data)

    gen._parse_orari_classi()

    assert '1A' in gen.orari_classi
    assert gen.orari_classi['1A']['LUNEDÌ'] == ['Rossi', 'Bianchi']
    assert gen.orari_classi['1A']['MARTEDÌ'] == ['Verdi']

    assert '2B' in gen.orari_classi
    assert gen.orari_classi['2B']['LUNEDÌ'] == ['Neri']
    assert gen.orari_classi['2B']['MARTEDÌ'] == ['Gialli', 'Blu']

def test_parse_orari_classi_empty():
    gen = MockGenerator()
    gen.giorni_settimana = ['LUNEDÌ', 'MARTEDÌ']
    gen.classi_df = pd.DataFrame(data=[])

    gen._parse_orari_classi()

    assert gen.orari_classi == {}

def test_parse_orari_classi_missing_column():
    gen = MockGenerator()
    gen.giorni_settimana = ['LUNEDÌ', 'MARTEDÌ']

    data = [
        {'CLASSE': '1A', 'DOC LUNEDÌ': 'Rossi;Bianchi'} # Missing DOC MARTEDÌ
    ]
    gen.classi_df = pd.DataFrame(data=data)

    with pytest.raises(KeyError):
        gen._parse_orari_classi()
