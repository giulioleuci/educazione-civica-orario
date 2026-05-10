import pytest
from datetime import datetime
from collections import defaultdict
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self, slots_by_key):
        self.slots_by_key = slots_by_key

def test_create_calendario_basic():
    # Setup
    date_1 = datetime(2023, 10, 23)
    date_2 = datetime(2023, 10, 24)
    slots_by_key = {
        'slot_1': {
            'CLASSE': '1A',
            'DATA': date_1,
            'GIORNO': 'Lunedì',
            'ORA': '1',
            'DOCENTE_SOSTITUITO': 'Prof_X'
        },
        'slot_2': {
            'CLASSE': '2B',
            'DATA': date_2,
            'GIORNO': 'Martedì',
            'ORA': '2',
            'DOCENTE_SOSTITUITO': 'Prof_Y'
        }
    }

    gen = MockGenerator(slots_by_key)

    individuo = {
        'slot_1': 'Prof_Civics_A',
        'slot_2': 'Prof_Civics_B'
    }

    # Execution
    calendario = gen.create_calendario(individuo)

    # Verification
    assert len(calendario) == 2

    # Check slot_1
    c_1 = next(item for item in calendario if item['CLASSE'] == '1A')
    assert c_1['CLASSE'] == '1A'
    assert c_1['DATA'] == '23/10/2023'
    assert c_1['GIORNO'] == 'Lunedì'
    assert c_1['ORA'] == '1'
    assert c_1['DOCENTE_CIVICS'] == 'Prof_Civics_A'
    assert c_1['DOCENTE_SOSTITUITO'] == 'Prof_X'

    # Check slot_2
    c_2 = next(item for item in calendario if item['CLASSE'] == '2B')
    assert c_2['CLASSE'] == '2B'
    assert c_2['DATA'] == '24/10/2023'
    assert c_2['GIORNO'] == 'Martedì'
    assert c_2['ORA'] == '2'
    assert c_2['DOCENTE_CIVICS'] == 'Prof_Civics_B'
    assert c_2['DOCENTE_SOSTITUITO'] == 'Prof_Y'

def test_create_calendario_empty():
    gen = MockGenerator({})
    individuo = {}
    calendario = gen.create_calendario(individuo)
    assert isinstance(calendario, list)
    assert len(calendario) == 0
