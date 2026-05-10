import pytest
from unittest.mock import patch
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self):
        # Bypass the original __init__ to avoid file loading and initialization logic
        pass

@patch('random.choices')
def test_selezione_basic(mock_choices):
    gen = MockGenerator()
    popolazione = ['ind1', 'ind2', 'ind3']
    fitness = [10.0, 5.0, 20.0]

    mock_choices.return_value = ['ind2', 'ind2', 'ind1']

    result = gen.selezione(popolazione, fitness)

    # Population should be sorted by fitness ascending:
    # 5.0 -> 'ind2' (rank 3)
    # 10.0 -> 'ind1' (rank 2)
    # 20.0 -> 'ind3' (rank 1)

    # total_rank = 3 + 2 + 1 = 6
    # probs = [3/6, 2/6, 1/6] = [0.5, 0.3333333333333333, 0.16666666666666666]

    expected_sorted_pop = ['ind2', 'ind1', 'ind3']
    expected_probs = [3/6, 2/6, 1/6]

    mock_choices.assert_called_once_with(
        expected_sorted_pop,
        weights=expected_probs,
        k=3
    )
    assert result == ['ind2', 'ind2', 'ind1']

@patch('random.choices')
def test_selezione_single_element(mock_choices):
    gen = MockGenerator()
    popolazione = ['ind1']
    fitness = [10.0]

    mock_choices.return_value = ['ind1']

    result = gen.selezione(popolazione, fitness)

    expected_sorted_pop = ['ind1']
    expected_probs = [1.0] # 1/1

    mock_choices.assert_called_once_with(
        expected_sorted_pop,
        weights=expected_probs,
        k=1
    )
    assert result == ['ind1']

@patch('random.choices')
def test_selezione_identical_fitness(mock_choices):
    gen = MockGenerator()
    popolazione = ['ind1', 'ind2', 'ind3']
    fitness = [10.0, 10.0, 10.0]

    mock_choices.return_value = ['ind1', 'ind2', 'ind3']

    result = gen.selezione(popolazione, fitness)

    # In case of identical fitness, Python's stable sort will preserve the original order.
    # Therefore, 'ind1' is first, 'ind2' is second, 'ind3' is third.
    # total_rank = 6. Probs = [3/6, 2/6, 1/6]

    expected_sorted_pop = ['ind1', 'ind2', 'ind3']
    expected_probs = [3/6, 2/6, 1/6]

    mock_choices.assert_called_once_with(
        expected_sorted_pop,
        weights=expected_probs,
        k=3
    )
    assert result == ['ind1', 'ind2', 'ind3']
