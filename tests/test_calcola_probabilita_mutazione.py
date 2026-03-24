import pytest
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self, base_prob, base_elite):
        self.base_probabilita_mutazione = base_prob
        self.base_elitismo_rate = base_elite

def test_calcola_probabilita_mutazione_zero_generations():
    gen = MockGenerator(base_prob=0.2, base_elite=0.01)
    assert gen.calcola_probabilita_mutazione(0) == 0.2

def test_calcola_probabilita_mutazione_some_generations():
    gen = MockGenerator(base_prob=0.2, base_elite=0.01)
    # 0.2 * (1 + 5/10) = 0.2 * 1.5 = 0.3
    assert gen.calcola_probabilita_mutazione(5) == pytest.approx(0.3)

def test_calcola_probabilita_mutazione_max_cap():
    gen = MockGenerator(base_prob=0.2, base_elite=0.01)
    # 0.2 * (1 + 20/10) = 0.2 * 3.0 = 0.6 -> capped at 0.5
    assert gen.calcola_probabilita_mutazione(20) == 0.5

def test_calcola_probabilita_mutazione_base_already_high():
    gen = MockGenerator(base_prob=0.6, base_elite=0.01)
    # base is 0.6, so even at 0 generations, it should be capped at 0.5
    assert gen.calcola_probabilita_mutazione(0) == 0.5

def test_calcola_elitismo_rate_zero_generations():
    gen = MockGenerator(base_prob=0.2, base_elite=0.01)
    assert gen.calcola_elitismo_rate(0) == 0.01

def test_calcola_elitismo_rate_some_generations():
    gen = MockGenerator(base_prob=0.2, base_elite=0.01)
    # 0.01 * (1 + 5/10) = 0.01 * 1.5 = 0.015
    assert gen.calcola_elitismo_rate(5) == pytest.approx(0.015)

def test_calcola_elitismo_rate_max_cap():
    gen = MockGenerator(base_prob=0.2, base_elite=0.05)
    # 0.05 * (1 + 15/10) = 0.05 * 2.5 = 0.125 -> capped at 0.1
    assert gen.calcola_elitismo_rate(15) == 0.1

def test_calcola_elitismo_rate_base_already_high():
    gen = MockGenerator(base_prob=0.2, base_elite=0.15)
    # base is 0.15, capped at 0.1
    assert gen.calcola_elitismo_rate(0) == 0.1
