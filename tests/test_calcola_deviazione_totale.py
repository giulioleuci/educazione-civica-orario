import pytest
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self, classi_list):
        # Bypass the original __init__ to avoid file loading and initialization logic
        self.classi_list = classi_list

def test_calcola_deviazione_totale_empty():
    gen = MockGenerator(['1A', '2B'])
    ore = {}
    assert gen._calcola_deviazione_totale(ore) == 0

def test_calcola_deviazione_totale_no_deviation():
    gen = MockGenerator(['1A', '2B'])
    ore = {
        '1A': {1: 1, 2: 0, 3: 1},
        '2B': {1: 1, 4: 1}
    }
    assert gen._calcola_deviazione_totale(ore) == 0

def test_calcola_deviazione_totale_single_deviation():
    gen = MockGenerator(['1A', '2B'])
    ore = {
        '1A': {1: 2, 2: 1},
        '2B': {1: 1}
    }
    assert gen._calcola_deviazione_totale(ore) == 1

def test_calcola_deviazione_totale_multiple_deviations():
    gen = MockGenerator(['1A', '2B', '3C'])
    ore = {
        '1A': {1: 3, 2: 2}, # (3-1) + (2-1) = 3
        '2B': {1: 1, 3: 4}, # (1-1) + (4-1) = 3
        '3C': {1: 0}        # 0
    }
    assert gen._calcola_deviazione_totale(ore) == 6

def test_calcola_deviazione_totale_ignore_extra_classes():
    gen = MockGenerator(['1A'])
    ore = {
        '1A': {1: 1},
        '2B': {1: 5}
    }
    assert gen._calcola_deviazione_totale(ore) == 0
