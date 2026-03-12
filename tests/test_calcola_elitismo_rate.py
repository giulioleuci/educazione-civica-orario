import pytest
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self, base_elitismo_rate):
        self.base_elitismo_rate = base_elitismo_rate

def test_calcola_elitismo_rate_zero_generations():
    # Setup
    gen = MockGenerator(base_elitismo_rate=0.01)

    # Input: 0 generations without improvement
    rate = gen.calcola_elitismo_rate(0)

    # Verify
    assert rate == 0.01

def test_calcola_elitismo_rate_scaling():
    # Setup
    gen = MockGenerator(base_elitismo_rate=0.01)

    # Input: 5 generations without improvement
    # Expected: 0.01 * (1 + 5/10) = 0.01 * 1.5 = 0.015
    rate = gen.calcola_elitismo_rate(5)

    # Verify
    assert rate == pytest.approx(0.015)

def test_calcola_elitismo_rate_scaling_more():
    # Setup
    gen = MockGenerator(base_elitismo_rate=0.01)

    # Input: 10 generations without improvement
    # Expected: 0.01 * (1 + 10/10) = 0.01 * 2 = 0.02
    rate = gen.calcola_elitismo_rate(10)

    # Verify
    assert rate == pytest.approx(0.02)

def test_calcola_elitismo_rate_cap():
    # Setup
    gen = MockGenerator(base_elitismo_rate=0.05)

    # Input: 20 generations without improvement
    # Expected calculation: 0.05 * (1 + 20/10) = 0.05 * 3 = 0.15
    # Cap should limit it to 0.1
    rate = gen.calcola_elitismo_rate(20)

    # Verify
    assert rate == 0.1

def test_calcola_elitismo_rate_high_base_rate():
    # Setup
    gen = MockGenerator(base_elitismo_rate=0.15)

    # Input: 0 generations without improvement
    # Expected calculation: 0.15 * (1 + 0/10) = 0.15
    # Cap should limit it to 0.1
    rate = gen.calcola_elitismo_rate(0)

    # Verify
    assert rate == 0.1
