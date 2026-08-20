import pytest

from find_range import find_range


@pytest.mark.parametrize(
    ("numbers", "expected"),
    [
        pytest.param([1, 2, 3, 4, 5], 4, id="ascending-positive-integers"),
        pytest.param([5, 4, 3, 2, 1], 4, id="descending-positive-integers"),
        pytest.param([3, 1, 5, 2, 4], 4, id="unordered-positive-integers"),
        pytest.param([-5, -2, -9, -1], 8, id="negative-integers"),
        pytest.param([-5, 0, 7], 12, id="negative-zero-and-positive"),
        pytest.param([0, 0, 0], 0, id="all-zero"),
        pytest.param([4, 4, 4, 4], 0, id="all-identical"),
        pytest.param([1, 5, 1, 5, 3], 4, id="duplicate-min-and-max"),
        pytest.param([42], 0, id="single-element"),
        pytest.param([-3.5, 1.25, 2.5], 6.0, id="floating-point-values"),
        pytest.param([1, 2.5, -3], 5.5, id="mixed-integers-and-floats"),
        pytest.param(
            [-(10**100), 0, 10**100],
            2 * 10**100,
            id="arbitrarily-large-integers",
        ),
        pytest.param((9, 2, 6), 7, id="tuple-input"),
    ],
)
def test_find_range_returns_difference_between_maximum_and_minimum(
    numbers, expected
):
    """代表的な数値シーケンスで最大値と最小値の差を返す。"""
    assert find_range(numbers) == pytest.approx(expected)


@pytest.mark.parametrize("empty_numbers", [[], ()], ids=["empty-list", "empty-tuple"])
def test_find_range_rejects_empty_sequence(empty_numbers):
    """空のシーケンスは範囲を定義できないため ValueError にする。"""
    with pytest.raises(ValueError, match="数値リストが空です"):
        find_range(empty_numbers)


@pytest.mark.parametrize(
    "invalid_numbers",
    [
        pytest.param(["1", "2"], id="strings-only"),
        pytest.param([1, "2", 3], id="mixed-number-and-string"),
    ],
)
def test_find_range_rejects_non_numeric_elements(invalid_numbers):
    """数値として比較・減算できない要素を含む入力は TypeError にする。"""
    with pytest.raises(TypeError):
        find_range(invalid_numbers)


def test_find_range_does_not_modify_input_list():
    """計算の前後で呼び出し元のリスト内容と順序を変更しない。"""
    numbers = [3, 1, 2]
    original = numbers.copy()

    find_range(numbers)

    assert numbers == original
