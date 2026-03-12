import pytest
from generator_mod import CalendarioGenerator

class MockGeneratorProb(CalendarioGenerator):
    def __init__(self, base_prob):
        # Override __init__ to avoid full initialization and file loading
        self.base_probabilita_mutazione = base_prob

def test_calcola_probabilita_mutazione_zero_generations():
    # Setup
    gen = MockGeneratorProb(0.2)

    # Run & Verify
    # With 0 generations, it should return exactly the base probability
    assert gen.calcola_probabilita_mutazione(0) == 0.2

def test_calcola_probabilita_mutazione_increase():
    # Setup
    gen = MockGeneratorProb(0.2)

    # Run & Verify
    # With 5 generations: 0.2 * (1 + 5/10) = 0.2 * 1.5 = 0.3
    assert gen.calcola_probabilita_mutazione(5) == pytest.approx(0.3)

def test_calcola_probabilita_mutazione_cap():
    # Setup
    gen = MockGeneratorProb(0.2)

    # Run & Verify
    # With 20 generations: 0.2 * (1 + 20/10) = 0.2 * 3.0 = 0.6
    # This should be capped at 0.5
    assert gen.calcola_probabilita_mutazione(20) == 0.5

def test_calcola_probabilita_mutazione_high_base():
    # Setup
    gen = MockGeneratorProb(0.6)

    # Run & Verify
    # If base probability is already > 0.5, it should be capped at 0.5 even with 0 generations
    assert gen.calcola_probabilita_mutazione(0) == 0.5

def test_calcola_probabilita_mutazione_negative_generations():
    # Setup
    gen = MockGeneratorProb(0.2)

    # Run & Verify
    # While typically not expected, we should see how it handles negative values conceptually.
    # -5 generations: 0.2 * (1 + -5/10) = 0.2 * 0.5 = 0.1
    assert gen.calcola_probabilita_mutazione(-5) == pytest.approx(0.1)

def test_calcola_probabilita_mutazione_float_generations():
    # Setup
    gen = MockGeneratorProb(0.2)

    # Run & Verify
    # With 2.5 generations: 0.2 * (1 + 2.5/10) = 0.2 * 1.25 = 0.25
    assert gen.calcola_probabilita_mutazione(2.5) == pytest.approx(0.25)
