
import sys
from unittest.mock import MagicMock
import importlib.util
import os

# Mock dependencies
mock_pd = MagicMock()
sys.modules['pandas'] = mock_pd

# Mock DataFrame to return data if it's already a dict/list that behaves like what we need
# or just return a mock that we can configure.
# For our purposes, we'll make pd.DataFrame return an object that behaves like a DataFrame.
class MockDataFrame:
    def __init__(self, data=None, **kwargs):
        self.data = data
        self.empty = (data is None or len(data) == 0)

    def to_excel(self, *args, **kwargs):
        pass

    def to_csv(self, *args, **kwargs):
        pass

    def map(self, func):
        if isinstance(self.data, list):
            return MockDataFrame([ {k: func(v) for k, v in item.items()} if isinstance(item, dict) else func(item) for item in self.data ])
        return self

    def applymap(self, func):
        return self.map(func)

    def iterrows(self):
        if isinstance(self.data, list):
            return enumerate(self.data)
        return enumerate([])

    def __getitem__(self, key):
        if isinstance(self.data, dict):
            return self.data[key]
        if isinstance(self.data, list):
            # very basic mock for classi_df['CLASSE']
            return [item[key] for item in self.data if key in item]
        return []

mock_pd.DataFrame.side_effect = MockDataFrame

mock_np = MagicMock()
class MockBool:
    pass
mock_np.bool_ = MockBool
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
