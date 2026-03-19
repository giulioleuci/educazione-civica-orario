import pytest
from unittest.mock import patch
# generator_mod is imported from tests/conftest.py which handles the hyphenated filename
from generator_mod import _get_excel_styles

def test_get_excel_styles():
    # We patch the classes in openpyxl.styles because they are imported inside the function
    with patch('generator_mod.PatternFill') as mock_fill, \
         patch('generator_mod.Border') as mock_border, \
         patch('generator_mod.Side') as mock_side, \
         patch('generator_mod.Alignment') as mock_alignment, \
         patch('generator_mod.Font') as mock_font:

        # Configure mocks to return distinct values for identification
        mock_fill.side_effect = lambda **kwargs: f"Fill_{kwargs.get('start_color')}"
        mock_border.return_value = "Border_Object"
        mock_side.side_effect = lambda **kwargs: f"Side_{kwargs.get('style')}"
        mock_alignment.return_value = "Alignment_Object"
        mock_font.return_value = "Font_Object"

        styles = _get_excel_styles()

        # Verify keys
        assert set(styles.keys()) == {
            'header_fill', 'week_fill', 'thin_border', 'centered_alignment', 'bold_font'
        }

        # Verify PatternFill calls
        assert styles['header_fill'] == "Fill_B8CCE4"
        assert styles['week_fill'] == "Fill_E6E6FA"

        # PatternFill(start_color='B8CCE4', end_color='B8CCE4', fill_type='solid')
        mock_fill.assert_any_call(start_color='B8CCE4', end_color='B8CCE4', fill_type='solid')
        # PatternFill(start_color='E6E6FA', end_color='E6E6FA', fill_type='solid')
        mock_fill.assert_any_call(start_color='E6E6FA', end_color='E6E6FA', fill_type='solid')

        # Verify Side calls
        # Side(style='thin') called 4 times for the border
        mock_side.assert_called_with(style='thin')
        assert mock_side.call_count == 4

        # Verify Border calls
        # Border(left=Side(...), right=Side(...), top=Side(...), bottom=Side(...))
        mock_border.assert_called_once_with(
            left="Side_thin",
            right="Side_thin",
            top="Side_thin",
            bottom="Side_thin"
        )
        assert styles['thin_border'] == "Border_Object"

        # Verify Alignment calls
        # Alignment(horizontal='center', vertical='center')
        mock_alignment.assert_called_once_with(horizontal='center', vertical='center')
        assert styles['centered_alignment'] == "Alignment_Object"

        # Verify Font calls
        # Font(bold=True)
        mock_font.assert_called_once_with(bold=True)
        assert styles['bold_font'] == "Font_Object"
