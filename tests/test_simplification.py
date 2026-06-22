"""Testes das transformações puras de simplificação."""
from spm.simplification import (
    coalescing_hidden,
    coalescing_repeating,
    get_dates,
    spell,
    split_by_grade,
    temporal_folding,
)


def _ev(*names, start=1):
    return [{"event": n, "time": start + i} for i, n in enumerate(names)]


def test_coalescing_repeating_removes_consecutive_duplicates():
    events = _ev("a", "a", "b")
    coalescing_repeating(events)
    assert [e["event"] for e in events] == ["a", "b"]


def test_coalescing_repeating_keeps_first_for_assignment_sub():
    # Para assignment_sub a regra remove o índice i (mantém o segundo).
    events = _ev("assignment_sub", "assignment_sub")
    coalescing_repeating(events)
    assert len(events) == 1
    assert events[0]["event"] == "assignment_sub"


def test_coalescing_hidden_removes_vis_try_sub_chain():
    events = _ev("assignment_vis", "assignment_try", "assignment_sub")
    coalescing_hidden(events, multilevel=False)
    assert [e["event"] for e in events] == ["assignment_sub"]


def test_coalescing_hidden_keeps_unrelated_events():
    events = _ev("course_vis", "assignment_sub")
    coalescing_hidden(events, multilevel=False)
    assert [e["event"] for e in events] == ["course_vis", "assignment_sub"]


def test_spell_marks_long_run_as_some():
    # Run de 4 "x" seguido de "y" (não-terminal): o primeiro vira _SOME.
    events = _ev("x", "x", "x", "x", "y")
    spell(events)
    assert events[0]["event"] == "x_SOME"


def test_temporal_folding_splits_on_large_gap():
    events = [
        {"event": "a", "time": 0},
        {"event": "b", "time": 100},
        {"event": "c", "time": 5000},   # gap 4900 > 3600 -> nova sessão
        {"event": "d", "time": 5100},
    ]
    sessions = temporal_folding(events, session_gap=3600)
    assert len(sessions) == 2
    assert [e["event"] for e in sessions[0]] == ["a", "b"]
    assert [e["event"] for e in sessions[1]] == ["c", "d"]


def test_temporal_folding_single_session_when_close():
    events = [{"event": "a", "time": 0}, {"event": "b", "time": 10}]
    assert len(temporal_folding(events, session_gap=3600)) == 1


def test_get_dates_reads_open_close(quiz_df):
    assert get_dates(quiz_df, 999) == (1000, 9000)


def test_split_by_grade_partitions_by_threshold():
    data = [
        {"key": "1", "grade": 2.0, "max_grade": 2.0},   # 100% -> high
        {"key": "2", "grade": 1.0, "max_grade": 2.0},   # 50%  -> high (>=)
        {"key": "3", "grade": 0.0, "max_grade": 2.0},   # 0%   -> low
    ]
    high, low = split_by_grade(data, threshold=0.5)
    assert {u["key"] for u in high} == {"1", "2"}
    assert {u["key"] for u in low} == {"3"}
