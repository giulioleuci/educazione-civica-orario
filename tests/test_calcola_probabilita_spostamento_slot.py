import pytest
from generator_mod import CalendarioGenerator


class DummyGenerator(CalendarioGenerator):
    def __init__(self):
        pass


def test_probabilita_spostamento_slot_base_e_cap():
    gen = DummyGenerator()
    assert gen.calcola_probabilita_spostamento_slot(0) == pytest.approx(0.002)
    assert gen.calcola_probabilita_spostamento_slot(10) == pytest.approx(0.004)
    assert gen.calcola_probabilita_spostamento_slot(1000) == pytest.approx(0.02)
