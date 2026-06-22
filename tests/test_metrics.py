"""Testes do núcleo de métricas (Jaccard, suportes, agregações)."""
from spm.metrics import (
    count_subsequence_occurrences,
    format_stat_with_std,
    get_supports,
    is_subsequence,
    jaccard_distance,
    jaccard_similarity,
    metrics,
    parse_mean_std,
)
from spm.mining import mine


def test_jaccard_identical_sequences():
    assert jaccard_similarity(["a", "b"], ["a", "b"]) == 1.0
    assert jaccard_distance(["a", "b"], ["a", "b"]) == 0.0


def test_jaccard_disjoint_sequences():
    assert jaccard_similarity(["a"], ["b"]) == 0.0
    assert jaccard_distance(["a"], ["b"]) == 100.0


def test_is_subsequence():
    assert is_subsequence(["a", "c"], ["a", "b", "c"]) is True
    assert is_subsequence(["c", "a"], ["a", "b", "c"]) is False
    assert is_subsequence([], ["a"]) is True


def test_count_subsequence_occurrences():
    assert count_subsequence_occurrences(["a", "b"], ["a", "b", "c"]) == 1
    assert count_subsequence_occurrences(["a", "b"], ["a", "b", "a", "b"]) == 3


def test_get_supports_uses_cache():
    formatted = [["a", "b", "c"], ["a", "b"]]
    cache = {}
    first = get_supports(formatted, 0.0, ["a", "b"], cache)
    assert first == 2
    assert tuple(["a", "b"]) in cache
    # segunda chamada vem do cache (mesmo resultado)
    assert get_supports(formatted, 0.0, ["a", "b"], cache) == 2


def test_format_and_parse_stat_round_trip():
    s = format_stat_with_std([1, 2, 3])
    assert s == "2.00 (+- 1.00)"
    assert parse_mean_std(s) == (2.0, 1.0)


def test_format_stat_single_value_has_zero_std():
    assert format_stat_with_std([5]) == "5.00 (+- 0)"


def test_metrics_end_to_end(sequences):
    mining_results = mine(sequences, minsup=0.5)
    final, general = metrics(mining_results, sequences, scenery="3-third", minsup=0.08)

    # general_info bem formado
    assert general["scenery"] == "3"          # split("-")[0]
    assert general["minsup"] == 0.08
    expected_total = sum(len(d["sequences"]) for d in mining_results.values())
    assert general["total_sequences"] == expected_total
    assert "jaccard_diversity" in general

    # cada padrão recebeu jaccard_distance e métricas básicas
    for data in final.values():
        for seq in data["sequences"]:
            assert "jaccard_distance" in seq
            assert "i_support" in seq
            assert seq["sequence_size"] == len(seq["sequence"])


def test_metrics_empty_returns_none():
    assert metrics({}, [], scenery="0") == (None, None)
