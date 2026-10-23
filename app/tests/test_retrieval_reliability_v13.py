from app.scripts.retrieval_reliability_v13 import percentile


def test_percentile_empty():
    assert percentile([], 95) == 0.0


def test_percentile_single():
    assert percentile([12], 95) == 12.0


def test_percentile_interpolation():
    assert percentile([10, 20, 30, 40], 50) == 25.0
    assert percentile([10, 20, 30, 40], 95) == 38.5


def test_percentile_unsorted():
    assert percentile([40, 10, 30, 20], 50) == 25.0
