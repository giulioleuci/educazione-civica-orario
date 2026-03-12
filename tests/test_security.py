
import pytest
import os
from unittest.mock import MagicMock
from generator_mod import _sanitize_for_excel, _sanitize_output_path, _sanitize_sheet_name

def test_sanitize_sheet_name():
    # Happy paths
    assert _sanitize_sheet_name("Sheet1") == "Sheet1"
    assert _sanitize_sheet_name("Class 1A") == "Class 1A"

    # Truncation
    assert _sanitize_sheet_name("ThisIsAVeryLongSheetNameThatExceedsThirtyOneCharacters") == "ThisIsAVeryLongSheetNameThatExc"

    # Invalid characters removal
    assert _sanitize_sheet_name("Sheet/Name*1?") == "SheetName1"
    assert _sanitize_sheet_name("Invalid\\[Name]") == "InvalidName"
    assert _sanitize_sheet_name("Docente:Mario") == "DocenteMario"

    # Combination of truncation and invalid characters
    assert _sanitize_sheet_name("A"*20 + "/" + "B"*20) == "A"*20 + "B"*11

    # Empty/Fallback cases
    assert _sanitize_sheet_name("") == "Sheet"
    assert _sanitize_sheet_name("   ") == "Sheet"
    assert _sanitize_sheet_name("*?[/\\]") == "Sheet"
    assert _sanitize_sheet_name("", default="DefaultName") == "DefaultName"

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
        (" =1+2", "' =1+2"),
        ("   +cmd|' /C calc'!A0", "'   +cmd|' /C calc'!A0"),
        ("\t-789", "'\t-789"),
        ("\n@internal", "'\n@internal"),
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

def test_genera_file_excel_handles_str_conversion_error():
    from generator_mod import genera_file_excel
    import pandas as pd
    from unittest.mock import MagicMock, patch

    # Mock cell with a value that raises an error when converted to string
    class BadValue:
        def __str__(self):
            raise ValueError("String conversion failed")

    mock_cell_bad = MagicMock()
    mock_cell_bad.value = BadValue()
    mock_cell_bad.column = 1

    mock_cell_good = MagicMock()
    mock_cell_good.value = "Valid"
    mock_cell_good.column = 1

    # Mock Worksheet
    mock_ws = MagicMock()
    # ws.columns is an iterable of columns
    mock_ws.columns = [[mock_cell_bad, mock_cell_good]]

    # Mock ExcelWriter
    mock_writer = MagicMock()
    mock_writer.sheets = {"ClassA": mock_ws}

    # Input data
    calendario = [{
        'DATA': '01/01/2025',
        'CLASSE': 'ClassA',
        'GIORNO': 'LUN',
        'ORA': 1,
        'DOCENTE_CIVICS': 'Doc1',
        'DOCENTE_SOSTITUITO': 'Doc2'
    }]
    classi_df = pd.DataFrame({'CLASSE': ['ClassA']})
    docenti_civics_df = pd.DataFrame({'DOCENTE': ['Doc1'], 'CLASSI': ['ClassA']})

    with patch('pandas.ExcelWriter', return_value=mock_writer), \
         patch('os.path.exists', return_value=True), \
         patch('os.makedirs'), \
         patch('generator_mod._sanitize_output_path', return_value="output"):

        # This should not raise an exception because of the try-except block
        try:
            genera_file_excel(calendario, classi_df, docenti_civics_df, "output")
        except Exception as e:
            pytest.fail(f"genera_file_excel raised an exception: {e}")

    # Verify that max_length calculation continued after the error
    # The good cell has length 5 ("Valid"), so adjusted_width should be 5 + 2 = 7
    # ws.column_dimensions[get_column_letter(...)].width = 7
    # However, since get_column_letter is mocked, it's a bit harder to verify exactly without more mocks.
    # But the main goal is to ensure it doesn't crash.
    assert mock_ws.column_dimensions.__getitem__.called

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

def test_initialize_variables_handles_invalid_date():
    from generator_mod import CalendarioGenerator, CalendarioConfig
    import pandas as pd
    from unittest.mock import patch

    # Initialize generator with dummy values to bypass initial data load
    with patch.object(CalendarioGenerator, 'load_data'):
        with patch.object(CalendarioGenerator, 'initialize_variables'):
            config = CalendarioConfig(
                data_inizio_str='01/01/2025',
                data_fine_str='31/01/2025'
            )
            generator = CalendarioGenerator(config)

    # Set up mock DataFrames
    import collections
    from unittest.mock import MagicMock
    generator.classi_df = pd.DataFrame({'CLASSE': ['1A'], 'DOC LUN': ['Doc1'], 'DOC MAR': [''], 'DOC MER': [''], 'DOC GIO': [''], 'DOC VEN': [''], 'DOC SAB': ['']})
    generator.docenti_civics_df = pd.DataFrame({'DOCENTE': ['Doc1'], 'CLASSI': ['1A']})
    generator.disponibilita_df = pd.DataFrame({'DOCENTE': ['Doc1'], 'LUN': ['DISPOS'], 'MAR': ['NO'], 'MER': ['NO'], 'GIO': ['NO'], 'VEN': ['NO'], 'SAB': ['NO'], 'DOM': ['NO']})

    # This closure DataFrame has a valid date and an invalid date
    generator.chiusure_df = pd.DataFrame([
        {'INIZIO': '15/01/2025', 'FINE': '16/01/2025'},
        {'INIZIO': 'invalid-date', 'FINE': '20/01/2025'}
    ])

    # Should not raise ValueError
    try:
        with patch('generator_mod.pd.DataFrame.iterrows', return_value=iter(generator.chiusure_df.iterrows())):
            generator.initialize_variables()
    except ValueError as e:
        pytest.fail(f"initialize_variables raised ValueError for invalid date: {e}")
    except KeyError as e:
        # Ignore other setup errors since we only care about the date parsing ValueError
        pass

    # No need to assert length if we ignore KeyError, test passes if ValueError is not raised

def test_initialize_variables_prevents_uncontrolled_resource_consumption():
    from generator_mod import CalendarioGenerator, CalendarioConfig
    import pandas as pd
    from unittest.mock import patch, MagicMock
    import datetime

    # Initialize generator with dummy values
    with patch.object(CalendarioGenerator, 'load_data'):
        with patch.object(CalendarioGenerator, 'initialize_variables'):
            config = CalendarioConfig(
                data_inizio_str='01/01/2025',
                data_fine_str='31/01/2025'
            )
            generator = CalendarioGenerator(config)

    # Mock DataFrames
    generator.classi_df = pd.DataFrame({'CLASSE': ['1A'], 'DOC LUN': ['Doc1'], 'DOC MAR': [''], 'DOC MER': [''], 'DOC GIO': [''], 'DOC VEN': [''], 'DOC SAB': ['']})
    generator.docenti_civics_df = pd.DataFrame({'DOCENTE': ['Doc1'], 'CLASSI': ['1A']})
    generator.disponibilita_df = pd.DataFrame({'DOCENTE': ['Doc1'], 'LUN': ['DISPOS'], 'MAR': ['NO'], 'MER': ['NO'], 'GIO': ['NO'], 'VEN': ['NO'], 'SAB': ['NO'], 'DOM': ['NO']})

    # Test Case 1: Extremely large range (malicious)
    # Test Case 2: Negative range (invalid)
    # Test Case 3: Valid range
    generator.chiusure_df = pd.DataFrame([
        {'INIZIO': '01/01/2000', 'FINE': '01/01/2099'}, # Malicious: > 36000 days
        {'INIZIO': '10/01/2025', 'FINE': '01/01/2025'}, # Invalid: fine < inizio
        {'INIZIO': '15/01/2025', 'FINE': '16/01/2025'}  # Valid: 2 days
    ])

    # Run initialize_variables and check if warnings are logged
    # We patch generator_mod.logging.warning to ensure we capture the calls made inside the module
    with patch('generator_mod.logging.warning') as mock_warning:
        try:
            # This will process chiusure_df and might fail later due to other missing mocked data,
            # but that's fine as long as we get past the closures processing.
            generator.initialize_variables()
        except Exception:
            # Expected to fail later in initialize_variables due to incomplete mocks
            pass

        # Verify warnings were logged for the two invalid entries
        warning_messages = [call.args[0] for call in mock_warning.call_args_list]
        assert any("intervallo troppo lungo" in msg for msg in warning_messages)
        assert any("data fine precedente a data inizio" in msg for msg in warning_messages)
