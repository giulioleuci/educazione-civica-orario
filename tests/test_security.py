
import pytest
import os
from unittest.mock import MagicMock
from generator_mod import _sanitize_for_excel, _sanitize_output_path

def test_sanitize_output_path():
    # Happy paths
    assert _sanitize_output_path("output") == "output"
    assert _sanitize_output_path("my_folder/sub") == os.path.normpath("my_folder/sub")

    # Edge cases
    assert _sanitize_output_path("") == "CALENDARIO_GENERATO"
    assert _sanitize_output_path(None) == "CALENDARIO_GENERATO"
    assert _sanitize_output_path(".") == "CALENDARIO_GENERATO"
    assert _sanitize_output_path("./") == "CALENDARIO_GENERATO"

    # Security scenarios: Absolute paths
    # os.path.basename will be returned
    assert _sanitize_output_path("/absolute/path") == "path"
    assert _sanitize_output_path("C:\\Windows") in ["Windows", "C:\\Windows"] # depends on OS, but basename is the goal
    # Actually, on Linux, C:\Windows is not absolute.

    # Security scenarios: Path traversal
    assert _sanitize_output_path("../traversal") == "traversal"
    assert _sanitize_output_path("../../etc/passwd") == "passwd"
    assert _sanitize_output_path("subdir/../../traversal") == "traversal"

    # Cases that resolve to empty/dot after basename
    assert _sanitize_output_path("..") == "CALENDARIO_GENERATO"
    assert _sanitize_output_path("/") == "CALENDARIO_GENERATO"

def test_sanitize_val_logic():
    # Extract the logic by passing a mock that has the expected behavior
    # We'll use a simple object to test the internal sanitize_val function behavior

    class MockDataFrame:
        def __init__(self, values):
            self.values = values
            self.empty = len(values) == 0

        def applymap(self, func):
            return [func(v) for v in self.values]

    # Test cases: (input, expected_output)
    test_cases = [
        ("=1+2", "'=1+2"),
        ("+456", "'+456"),
        ("-789", "'-789"),
        ("@internal", "'@internal"),
        ("Normal text", "Normal text"),
        ("123", "123"),
        (123, 123),
        (None, None),
        ("", ""),
        (" ", " "),
    ]

    for inp, exp in test_cases:
        df = MockDataFrame([inp])
        result = _sanitize_for_excel(df)
        assert result[0] == exp

def test_sanitize_for_excel_empty():
    mock_df = MagicMock()
    mock_df.empty = True
    result = _sanitize_for_excel(mock_df)
    assert result == mock_df
    assert not mock_df.applymap.called
    if hasattr(mock_df, 'map'):
        assert not mock_df.map.called

def test_sanitize_for_excel_calls_map_if_present():
    mock_df = MagicMock()
    mock_df.empty = False
    # mock_df has 'map' by default because it's a MagicMock
    _sanitize_for_excel(mock_df)
    assert mock_df.map.called

def test_sanitize_for_excel_calls_applymap_if_map_absent():
    mock_df = MagicMock()
    mock_df.empty = False
    del mock_df.map
    _sanitize_for_excel(mock_df)
    assert mock_df.applymap.called
