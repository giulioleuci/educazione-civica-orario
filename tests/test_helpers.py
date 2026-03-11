
from unittest.mock import MagicMock
from generator_mod import (
    calcola_fitness_helper,
    genera_individuo_greedy_helper,
    genera_individuo_batch_helper,
    genera_individuo_random_helper
)

def test_calcola_fitness_helper():
    mock_self = MagicMock()
    individuo = {'slot1': 'Docente1'}
    args = (mock_self, individuo)

    result = calcola_fitness_helper(args)

    mock_self.calcola_fitness.assert_called_once_with(individuo)
    assert result == mock_self.calcola_fitness.return_value

def test_genera_individuo_greedy_helper():
    mock_self = MagicMock()
    args = (mock_self, None)

    result = genera_individuo_greedy_helper(args)

    mock_self.genera_individuo_greedy.assert_called_once_with(None)
    assert result == mock_self.genera_individuo_greedy.return_value

def test_genera_individuo_batch_helper():
    mock_self = MagicMock()
    args = (mock_self, None)

    result = genera_individuo_batch_helper(args)

    mock_self.genera_individuo_batch.assert_called_once_with(None)
    assert result == mock_self.genera_individuo_batch.return_value

def test_genera_individuo_random_helper():
    mock_self = MagicMock()
    args = (mock_self, None)

    result = genera_individuo_random_helper(args)

    mock_self.genera_individuo_random.assert_called_once_with(None)
    assert result == mock_self.genera_individuo_random.return_value
