def find_range(numbers):
    if not numbers:
        raise ValueError("数値リストが空です")

    return max(numbers) - min(numbers)
