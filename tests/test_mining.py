"""Testes do núcleo de mineração (PrefixSpan / mine)."""
from spm.mining import build_mining_output, mine, prefix_mining


def test_prefix_mining_finds_frequent_pattern():
    # ["a","b"] aparece em 3 de 4 sequências.
    formatted = [["a", "b", "c"], ["a", "b"], ["a", "b", "d"], ["x", "y"]]
    result = prefix_mining(formatted, minsup=0.5)   # min_support = 2
    # result[1] = padrões de tamanho 2
    patterns = {k: v for k, v in result[1].items()}
    assert "['a', 'b']" in patterns
    assert patterns["['a', 'b']"] == 3


def test_mine_returns_structured_dict(sequences):
    result = mine(sequences, minsup=0.5)
    assert "2_sequences" in result
    seqs = [s["sequence"] for s in result["2_sequences"]["sequences"]]
    assert ["a", "b"] in seqs


def test_mine_minlen_excludes_single_events(sequences):
    # PrefixSpan usa minlen=2; não deve haver padrões de tamanho 1.
    result = mine(sequences, minsup=0.5)
    for s in result.get("1_sequences", {}).get("sequences", []):
        assert len(s["sequence"]) >= 2


def test_build_mining_output_shape():
    # Saída bruta do prefix_mining: lista por tamanho (1-indexed -> índice 0 vazio).
    raw = [{}, {"['a', 'b']": 3}]
    out = build_mining_output(raw)
    assert set(out.keys()) == {"1_sequences", "2_sequences"}
    assert out["2_sequences"]["sequences"] == [{"sequence": ["a", "b"], "total": 3}]
