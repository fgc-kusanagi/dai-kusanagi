import pytest
from find_range import find_range

def test_nomal():
    assert find_range([1, 2, 3, 4, 5]) == 4

def test_single():
    assert find_range([5]) == 0

def test_negative_numbers():
    assert find_range([-3, -1, 2, 5]) == 8

def test_empty_list():
    with pytest.raises(ValueError):
        find_range([])
