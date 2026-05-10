import pytest
from unittest.mock import patch
from generator_mod import CalendarioGenerator

class MockGenerator(CalendarioGenerator):
    def __init__(self):
        # Bypass the original __init__ to avoid file loading and initialization logic
        pass

def test_identify_blocks_empty():
    gen = MockGenerator()
    blocks = gen.identify_blocks({}, {})
    assert blocks == []

@patch('random.shuffle')
def test_identify_blocks_small_input(mock_shuffle):
    # Length < 10, block_size = max(1, len // 10) -> 1
    # We provide exactly 5 keys
    genitore1 = {'k1': 1, 'k2': 2, 'k3': 3, 'k4': 4, 'k5': 5}
    genitore2 = {'k1': 10, 'k2': 20, 'k3': 30, 'k4': 40, 'k5': 50}

    # Do nothing on shuffle so the keys remain in the same order
    mock_shuffle.side_effect = lambda x: None

    gen = MockGenerator()
    blocks = gen.identify_blocks(genitore1, genitore2)

    assert len(blocks) == 5
    for i, k in enumerate(['k1', 'k2', 'k3', 'k4', 'k5']):
        assert blocks[i] == {'genitore1': {k: genitore1[k]}, 'genitore2': {k: genitore2[k]}}

@patch('random.shuffle')
def test_identify_blocks_large_input(mock_shuffle):
    # Length 20, block_size = max(1, 20 // 10) -> 2
    genitore1 = {f'k{i}': i for i in range(20)}
    genitore2 = {f'k{i}': i * 10 for i in range(20)}

    mock_shuffle.side_effect = lambda x: None

    gen = MockGenerator()
    blocks = gen.identify_blocks(genitore1, genitore2)

    assert len(blocks) == 10

    # First block should have k0 and k1
    assert blocks[0] == {
        'genitore1': {'k0': 0, 'k1': 1},
        'genitore2': {'k0': 0, 'k1': 10}
    }

    # Last block should have k18 and k19
    assert blocks[9] == {
        'genitore1': {'k18': 18, 'k19': 19},
        'genitore2': {'k18': 180, 'k19': 190}
    }

@patch('random.shuffle')
def test_identify_blocks_missing_keys_in_gen2(mock_shuffle):
    # Test fallback: genitore2.get(k, genitore1[k])
    genitore1 = {'k1': 1, 'k2': 2}
    genitore2 = {'k1': 10} # k2 is missing

    mock_shuffle.side_effect = lambda x: None

    gen = MockGenerator()
    blocks = gen.identify_blocks(genitore1, genitore2)

    assert len(blocks) == 2
    assert blocks[0] == {'genitore1': {'k1': 1}, 'genitore2': {'k1': 10}}
    assert blocks[1] == {'genitore1': {'k2': 2}, 'genitore2': {'k2': 2}} # Fallback to gen1
