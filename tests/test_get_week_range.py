
from datetime import datetime
import pytest
from generator_mod import _get_week_range

def test_get_week_range_monday():
    # 2024-12-02 is a Monday
    date = datetime(2024, 12, 2)
    expected = "02/12/2024 - 07/12/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_midweek():
    # 2024-12-04 is a Wednesday
    date = datetime(2024, 12, 4)
    expected = "02/12/2024 - 07/12/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_saturday():
    # 2024-12-07 is a Saturday
    date = datetime(2024, 12, 7)
    expected = "02/12/2024 - 07/12/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_sunday():
    # 2024-12-08 is a Sunday
    date = datetime(2024, 12, 8)
    expected = "02/12/2024 - 07/12/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_leap_year():
    # 2024-02-29 is a Thursday
    date = datetime(2024, 2, 29)
    # Monday of that week is 26/02/2024
    # Saturday of that week is 02/03/2024
    expected = "26/02/2024 - 02/03/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_month_boundary():
    # 2024-11-30 is a Saturday
    date = datetime(2024, 11, 30)
    # Monday was 25/11/2024
    expected = "25/11/2024 - 30/11/2024"
    assert _get_week_range(date) == expected

def test_get_week_range_year_boundary():
    # 2025-01-01 is a Wednesday
    date = datetime(2025, 1, 1)
    # Monday was 30/12/2024
    # Saturday is 04/01/2025
    expected = "30/12/2024 - 04/01/2025"
    assert _get_week_range(date) == expected
