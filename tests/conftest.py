
import sys
from unittest.mock import MagicMock
import importlib.util
import os

# Mock dependencies
mock_pd = MagicMock()
sys.modules['pandas'] = mock_pd

# Mock DataFrame to return data if it's already a dict/list that behaves like what we need
# or just return a mock that we can configure.
# For our purposes, we'll make pd.DataFrame return the input data if it's a dict.
def mock_dataframe_init(data=None, **kwargs):
    return data

mock_pd.DataFrame.side_effect = mock_dataframe_init

mock_np = MagicMock()
sys.modules['numpy'] = mock_np

# Mock openpyxl (it is imported inside a function, but let's be safe)
sys.modules['openpyxl'] = MagicMock()
sys.modules['openpyxl.styles'] = MagicMock()
sys.modules['openpyxl.utils'] = MagicMock()

# Path to the generator script
script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../calendario-ed-civ-generator.py'))

# Import the module
spec = importlib.util.spec_from_file_location("generator_mod", script_path)
generator_mod = importlib.util.module_from_spec(spec)
# We need to add the module to sys.modules so it can be imported normally in tests
sys.modules['generator_mod'] = generator_mod
spec.loader.exec_module(generator_mod)
