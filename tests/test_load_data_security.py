
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import logging
from generator_mod import CalendarioGenerator, CalendarioConfig

def test_load_data_file_not_found():
    config = CalendarioConfig()

    with patch('pandas.read_csv') as mock_read:
        mock_read.side_effect = FileNotFoundError("File not found")

        with pytest.raises(SystemExit) as e:
            CalendarioGenerator(config)
        assert e.value.code == 1

def test_load_data_empty_data():
    config = CalendarioConfig()

    # Mocking pd.errors since it might not be in the mock
    if not hasattr(pd, 'errors'):
        pd.errors = MagicMock()

    pd.errors.EmptyDataError = type('EmptyDataError', (Exception,), {})

    with patch('pandas.read_csv') as mock_read:
        mock_read.side_effect = pd.errors.EmptyDataError("No data")

        with pytest.raises(SystemExit) as e:
            CalendarioGenerator(config)
        assert e.value.code == 1

def test_load_data_parser_error():
    config = CalendarioConfig()

    if not hasattr(pd, 'errors'):
        pd.errors = MagicMock()

    pd.errors.ParserError = type('ParserError', (Exception,), {})

    with patch('pandas.read_csv') as mock_read:
        mock_read.side_effect = pd.errors.ParserError("Parse error")

        with pytest.raises(SystemExit) as e:
            CalendarioGenerator(config)
        assert e.value.code == 1

def test_load_data_success_initializes_classi_list():
    config = CalendarioConfig()

    # Mock DataFrames
    mock_classi_df = pd.DataFrame([{'CLASSE': '1A'}, {'CLASSE': '1B'}])

    with patch('pandas.read_csv', return_value=mock_classi_df):
        # We need to mock the other 3 read_csv calls as well
        with patch('generator_mod.pd.read_csv') as mock_read:
            mock_read.return_value = mock_classi_df
            # Mocking initialize_variables to avoid further errors since we only test load_data
            with patch.object(CalendarioGenerator, 'initialize_variables'):
                gen = CalendarioGenerator(config)
                assert gen.classi_list == ['1A', '1B']
